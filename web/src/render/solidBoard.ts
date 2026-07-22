import {
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  FrontSide,
  Group,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Quaternion,
  Vector3,
} from "three";
import {
  newellNormal,
  normalize,
  type Board3D,
  type CellId,
  type Vec3,
} from "../boards/core";
import {
  COLORS,
  glyphFor,
  polygonInradius,
  type BoardMesh,
  type BoardView,
  type CellAnchor,
  type CellVisual,
} from "./boardMesh";
import { makeGlyphAtlas, type GlyphAtlas } from "./glyphAtlas";

// The 3D counterpart of PolygonBoard: a Board3D's outward-wound surface
// polygons become one merged beveled geometry — each cell an inset top face
// raised along its outward normal, ringed by bevel quads. Revealed cells
// drop their plateau to a sunken face (the classic minesweeper raised/flat
// distinction — colour alone is ambiguous under 3D lighting). Closed
// surfaces cull back faces; open or non-orientable surfaces (M3's cylinder /
// Möbius strip / Klein bottle) render DoubleSide with the back side dimmed
// in the shader, staying opaque so the depth buffer resolves
// self-intersections. Glyphs are billboards rebuilt from the current board
// rotation (`orient`), so numbers stay screen-upright like the pygame
// renderer, and only front-facing cells carry one.

const SHRINK = 0.04;
const BEVEL = 0.16;
// Lower relief than the flat renderer's 0.24: on a closed surface the cells
// tilt against each other, and tall plateaus on big curved cells (the
// sphere's pentagons) shingle over their neighbours at the silhouette.
const HEIGHT_FRAC = 0.1;
// Revealed cells sink almost to the base layer (kept just above it so the
// two never z-fight).
const FLAT_FRAC = 0.02;
const BACK_DIM = 0.82; // matches the pygame two-sided back-face dimming
const BASE_COLOR = "#8e8e8e"; // grout surface showing through the tile gaps

const _inv = /* @__PURE__ */ new Matrix4(); // scratch for the world→local map

// Wider hidden/revealed split than the flat palette: under 3D lighting the
// faces of a curved surface pick up large shading differences of their own,
// so the flat renderer's subtle tone step is not readable. Hidden tiles are
// darker (the pygame HIDDEN_FACE tone), opened ones clearly lighter.
const SOLID_COLORS: Record<CellVisual["kind"], Color> = {
  hidden: new Color("#b4b4b4"),
  flagged: new Color("#b4b4b4"),
  revealed: new Color("#efefef"),
  mine: new Color("#efefef"),
  exploded: COLORS.exploded,
};

interface CellGeom {
  start: number; // first vertex index in the position/normal/color buffers
  count: number; // vertex count for this cell (9 * polygon size)
  poly: Vec3[]; // the cell's surface polygon, outward wound
  centroid: Vec3;
  normal: Vec3; // outward unit normal
  radius: number; // mean distance centroid -> vertices
  center: Vec3; // centre of the (currently raised or sunken) top face
}

export class SolidBoard extends Group implements BoardMesh {
  readonly view: BoardView;
  private readonly order: CellId[];
  private readonly cellIndex = new Map<CellId, number>();
  private readonly geom: CellGeom[] = [];
  private readonly faceCell: Int32Array;
  private readonly positionAttr: BufferAttribute;
  private readonly normalAttr: BufferAttribute;
  private readonly colorAttr: BufferAttribute;
  private readonly glyphGeometry = new BufferGeometry();
  private readonly atlas: GlyphAtlas;
  private readonly states: CellVisual[];
  private hovered = -1;
  // Billboard basis in board-local coordinates: screen-right and screen-up,
  // updated from the current rotation. `cameraLocal` is the camera position
  // mapped into the same board-local frame, so a cell's visibility can be
  // tested per-cell against the true (perspective) viewing direction.
  private viewRight: Vec3 = [1, 0, 0];
  private viewUp: Vec3 = [0, 1, 0];
  private cameraLocal: Vec3 = [0, 0, 1];

  constructor(board: Board3D) {
    super();
    this.atlas = makeGlyphAtlas();
    this.order = [...board.polygons.keys()];
    this.states = this.order.map(() => ({ kind: "hidden" }));
    this.order.forEach((c, i) => this.cellIndex.set(c, i));
    this.view = { kind: "solid", radius: board.radius };

    const basePositions: number[] = [];
    const faceCell: number[] = [];
    let vertexCount = 0;

    this.order.forEach((cell, ci) => {
      const poly = board.polygons.get(cell)!;
      const n = poly.length;
      const centroid = centroidOf(poly);
      const normal = normalize(newellNormal(poly));
      const radius =
        poly.reduce(
          (s, p) =>
            s +
            Math.hypot(p[0] - centroid[0], p[1] - centroid[1], p[2] - centroid[2]),
          0,
        ) / n;
      this.geom.push({
        start: vertexCount,
        count: 9 * n, // 3n top-fan + 6n bevel-ring vertices
        poly,
        centroid,
        normal,
        radius,
        center: centroid,
      });
      vertexCount += 9 * n;
      for (let e = 0; e < n; e++) faceCell.push(ci, ci, ci); // 1 top + 2 bevel

      // Opaque base layer under the whole (unshrunk) polygon: the tile gaps
      // and the silhouette show this grout surface instead of seeing through
      // the hollow interior.
      for (let e = 0; e < n; e++) {
        for (const p of [centroid, poly[e]!, poly[(e + 1) % n]!]) {
          basePositions.push(p[0], p[1], p[2]);
        }
      }
    });

    this.faceCell = Int32Array.from(faceCell);
    const geometry = new BufferGeometry();
    this.positionAttr = new BufferAttribute(new Float32Array(vertexCount * 3), 3);
    this.normalAttr = new BufferAttribute(new Float32Array(vertexCount * 3), 3);
    this.colorAttr = new BufferAttribute(new Float32Array(vertexCount * 3), 3);
    geometry.setAttribute("position", this.positionAttr);
    geometry.setAttribute("normal", this.normalAttr);
    geometry.setAttribute("color", this.colorAttr);

    const material = new MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.65,
      metalness: 0,
      // Closed surfaces rely on back-face culling (winding is outward);
      // open/non-orientable ones draw both sides, back dimmed via the shader
      // patch below — opaque, so the depth buffer sorts self-intersections.
      side: board.twoSided ? DoubleSide : FrontSide,
    });
    if (board.twoSided) {
      material.onBeforeCompile = (shader) => {
        shader.fragmentShader = shader.fragmentShader.replace(
          "#include <dithering_fragment>",
          `#include <dithering_fragment>
  if (!gl_FrontFacing) gl_FragColor.rgb *= ${BACK_DIM};`,
        );
      };
    }
    const cells = new Mesh(geometry, material);
    cells.name = "cells";
    this.add(cells);

    if (!board.twoSided) {
      const baseGeometry = new BufferGeometry();
      baseGeometry.setAttribute(
        "position",
        new BufferAttribute(new Float32Array(basePositions), 3),
      );
      baseGeometry.computeVertexNormals();
      const base = new Mesh(
        baseGeometry,
        new MeshStandardMaterial({
          color: BASE_COLOR,
          roughness: 0.8,
          metalness: 0,
          flatShading: true,
          side: FrontSide,
        }),
      );
      base.name = "base";
      this.add(base);
    }

    const glyphMesh = new Mesh(
      this.glyphGeometry,
      new MeshBasicMaterial({
        map: this.atlas.texture,
        transparent: true,
        alphaTest: 0.4,
        // Billboards for front-facing cells only, drawn over the board like
        // the pygame renderer (no depth test — geometry can never clip a
        // number).
        depthWrite: false,
        depthTest: false,
      }),
    );
    glyphMesh.name = "glyphs";
    glyphMesh.renderOrder = 1;
    this.add(glyphMesh);

    for (let i = 0; i < this.order.length; i++) {
      this.writeGeometry(i);
      this.writeColor(i);
    }
    geometry.computeBoundingSphere();
    this.rebuildGlyphs();
  }

  get cellCount(): number {
    return this.order.length;
  }

  cellForFace(faceIndex: number): CellId | null {
    const ci = this.faceCell[faceIndex];
    return ci == null ? null : (this.order[ci] ?? null);
  }

  cellAnchor(cell: CellId): CellAnchor | null {
    const i = this.cellIndex.get(cell);
    if (i == null) return null;
    const g = this.geom[i]!;
    return { center: g.center, normal: g.normal };
  }

  setVisual(cell: CellId, visual: CellVisual): void {
    const i = this.cellIndex.get(cell);
    if (i == null) return;
    const wasFlat = isFlat(this.states[i]!);
    this.states[i] = visual;
    if (isFlat(visual) !== wasFlat) this.writeGeometry(i);
    this.writeColor(i);
    this.rebuildGlyphs();
  }

  setHover(cell: CellId | null): void {
    const i = cell == null ? -1 : (this.cellIndex.get(cell) ?? -1);
    if (i === this.hovered) return;
    const prev = this.hovered;
    this.hovered = i;
    if (prev >= 0) this.writeColor(prev);
    if (i >= 0) this.writeColor(i);
  }

  /** Update the billboard basis (screen-upright glyphs) from the board's
   * current rotation, and record the camera position in board-local space so
   * `rebuildGlyphs` can cull cells that face away under perspective. Called
   * by the renderer whenever the board turns, is (re)framed, or is set. */
  orient(rotation: Quaternion, cameraWorldPos: Vector3): void {
    const inverse = rotation.clone().invert();
    const toVec3 = (v: Vector3): Vec3 => [v.x, v.y, v.z];
    this.viewRight = toVec3(new Vector3(1, 0, 0).applyQuaternion(inverse));
    this.viewUp = toVec3(new Vector3(0, 1, 0).applyQuaternion(inverse));
    this.updateWorldMatrix(true, false);
    const camLocal = cameraWorldPos
      .clone()
      .applyMatrix4(_inv.copy(this.matrixWorld).invert());
    this.cameraLocal = [camLocal.x, camLocal.y, camLocal.z];
    this.rebuildGlyphs();
  }

  /** (Re)write one cell's beveled geometry: raised for hidden/flagged cells,
   * sunk nearly to the base layer once revealed. */
  private writeGeometry(i: number): void {
    const g = this.geom[i]!;
    const { poly, centroid, normal } = g;
    const n = poly.length;
    const height = g.radius * (isFlat(this.states[i]!) ? FLAT_FRAC : HEIGHT_FRAC);
    const lift: Vec3 = [normal[0] * height, normal[1] * height, normal[2] * height];
    const outer = poly.map((p) => lerp3(p, centroid, SHRINK));
    const top = poly.map((p) => add3(lerp3(p, centroid, SHRINK + BEVEL), lift));
    const topCenter = add3(centroid, lift);
    g.center = topCenter;

    let v = g.start;
    const put = (p: Vec3, nrm: Vec3) => {
      this.positionAttr.setXYZ(v, p[0], p[1], p[2]);
      this.normalAttr.setXYZ(v, nrm[0], nrm[1], nrm[2]);
      v++;
    };
    // top face: fan from the raised centroid (outward winding preserved —
    // the board's polygons are counterclockwise seen from outside). The
    // whole fan carries the cell normal, so a cell on a curved surface
    // (whose polygon is not planar — e.g. the sphere's pentagons) still
    // shades as one clean facet instead of a pinwheel of fan triangles.
    for (let e = 0; e < n; e++) {
      put(topCenter, normal);
      put(top[e]!, normal);
      put(top[(e + 1) % n]!, normal);
    }
    // bevel ring: outer edge on the surface up to the raised top edge.
    // One normal per quad keeps its two (slightly non-coplanar) triangles
    // from showing a diagonal shading crease.
    for (let e = 0; e < n; e++) {
      const a = e;
      const b = (e + 1) % n;
      const quadNormal = normalize(
        newellNormal([outer[a]!, outer[b]!, top[b]!, top[a]!]),
      );
      put(outer[a]!, quadNormal);
      put(outer[b]!, quadNormal);
      put(top[b]!, quadNormal);
      put(outer[a]!, quadNormal);
      put(top[b]!, quadNormal);
      put(top[a]!, quadNormal);
    }
    this.positionAttr.needsUpdate = true;
    this.normalAttr.needsUpdate = true;
  }

  private writeColor(i: number): void {
    const col = SOLID_COLORS[this.states[i]!.kind].clone();
    if (i === this.hovered && this.states[i]!.kind === "hidden") {
      col.offsetHSL(0, 0, 0.08);
    }
    const g = this.geom[i]!;
    for (let v = 0; v < g.count; v++) {
      this.colorAttr.setXYZ(g.start + v, col.r, col.g, col.b);
    }
    this.colorAttr.needsUpdate = true;
  }

  private rebuildGlyphs(): void {
    const pos: number[] = [];
    const uvs: number[] = [];
    const { viewRight: u, viewUp: v, cameraLocal: cam } = this;
    for (let i = 0; i < this.order.length; i++) {
      const glyph = glyphFor(this.states[i]!);
      if (glyph === null) continue;
      const uv = this.atlas.uv(glyph);
      if (!uv) continue;
      const g = this.geom[i]!;
      const c = g.center;
      // Only cells whose top face the camera can actually see carry a glyph
      // (the glyph mesh has no depth test, so a back cell's number would
      // otherwise bleed through the board). The direction from the cell to
      // the camera is computed per-cell, so the horizon is the true
      // perspective silhouette — a constant view-forward would keep cells
      // that have already curved onto the back near the rim.
      const toCam = normalize([cam[0] - c[0], cam[1] - c[1], cam[2] - c[2]]);
      if (
        toCam[0] * g.normal[0] +
          toCam[1] * g.normal[1] +
          toCam[2] * g.normal[2] <=
        0.05
      ) {
        continue;
      }
      // Fit the glyph inside the cell as the viewer sees it: project the
      // cell polygon into the billboard plane and size/centre the quad by
      // the projected footprint's inradius (as the pygame renderer does per
      // frame), so a number never crosses its cell's edges however tilted
      // the cell currently is.
      const projected = g.poly.map((p): [number, number] => {
        const d: Vec3 = [p[0] - c[0], p[1] - c[1], p[2] - c[2]];
        return [
          d[0] * u[0] + d[1] * u[1] + d[2] * u[2],
          d[0] * v[0] + d[1] * v[1] + d[2] * v[2],
        ];
      });
      const px =
        projected.reduce((a, q) => a + q[0], 0) / projected.length;
      const py =
        projected.reduce((a, q) => a + q[1], 0) / projected.length;
      const s = polygonInradius(projected, [px, py]) * 0.9;
      if (!(s > 0)) continue;
      const at = (du: number, dv: number): Vec3 => [
        c[0] + u[0] * (px + s * du) + v[0] * (py + s * dv),
        c[1] + u[1] * (px + s * du) + v[1] * (py + s * dv),
        c[2] + u[2] * (px + s * du) + v[2] * (py + s * dv),
      ];
      const bl = at(-1, -1);
      const br = at(1, -1);
      const tr = at(1, 1);
      const tl = at(-1, 1);
      const push = (p: Vec3) => pos.push(p[0], p[1], p[2]);
      push(bl);
      push(br);
      push(tr);
      push(bl);
      push(tr);
      push(tl);
      const [u0, v0, u1, v1] = uv;
      uvs.push(u0, v0, u1, v0, u1, v1, u0, v0, u1, v1, u0, v1);
    }
    this.glyphGeometry.setAttribute(
      "position",
      new BufferAttribute(new Float32Array(pos), 3),
    );
    this.glyphGeometry.setAttribute(
      "uv",
      new BufferAttribute(new Float32Array(uvs), 2),
    );
    this.glyphGeometry.computeBoundingSphere();
  }
}

/** Revealed cells (numbers, mines, the exploded cell) lie flat; hidden and
 * flagged cells stay raised. */
function isFlat(visual: CellVisual): boolean {
  return (
    visual.kind === "revealed" ||
    visual.kind === "mine" ||
    visual.kind === "exploded"
  );
}

function centroidOf(points: readonly Vec3[]): Vec3 {
  const c: Vec3 = [0, 0, 0];
  for (const p of points) {
    c[0] += p[0];
    c[1] += p[1];
    c[2] += p[2];
  }
  return [c[0] / points.length, c[1] / points.length, c[2] / points.length];
}

function lerp3(p: Vec3, q: Vec3, t: number): Vec3 {
  return [
    p[0] + (q[0] - p[0]) * t,
    p[1] + (q[1] - p[1]) * t,
    p[2] + (q[2] - p[2]) * t,
  ];
}

function add3(p: Vec3, q: Vec3): Vec3 {
  return [p[0] + q[0], p[1] + q[1], p[2] + q[2]];
}
