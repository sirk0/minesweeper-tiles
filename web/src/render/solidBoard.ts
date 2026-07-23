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
// polygons become one merged geometry. On a closed surface each cell is an
// inset top face raised along its outward normal, ringed by bevel quads;
// revealed cells drop their plateau to a sunken face (the classic minesweeper
// raised/flat distinction — colour alone is ambiguous under 3D lighting), and
// back faces are culled. On an open or non-orientable surface (M3's cylinder /
// Möbius strip / Klein bottle) each cell is instead a flat DoubleSide tile on
// the surface, lit and coloured identically from both faces, so it reads and
// plays the same from inside or out; grout under the tile gaps keeps them from
// becoming holes. Glyphs are billboards rebuilt from the current board rotation
// (`orient`) so numbers stay screen-upright like the pygame renderer, and are
// depth-tested so geometry in front of a cell hides its number (a nearer wall,
// a nearer frame bar) instead of letting it bleed through.

const SHRINK = 0.04;
const BEVEL = 0.16;
// Lower relief than the flat renderer's 0.24: on a closed surface the cells
// tilt against each other, and tall plateaus on big curved cells (the
// sphere's pentagons) shingle over their neighbours at the silhouette.
const HEIGHT_FRAC = 0.1;
// Revealed cells sink almost to the base layer (kept just above it so the
// two never z-fight).
const FLAT_FRAC = 0.02;
const BASE_COLOR = "#8e8e8e"; // grout surface showing through the tile gaps

const _inv = /* @__PURE__ */ new Matrix4(); // scratch for the world→local map

// Wider hidden/revealed split than the flat palette: under 3D lighting the
// faces of a curved surface pick up large shading differences of their own,
// so the flat renderer's subtle tone step is not readable. Hidden tiles are
// darker (the pygame HIDDEN_FACE tone), opened ones clearly lighter.
const SOLID_COLORS: Record<CellVisual["kind"], Color> = {
  hidden: new Color("#b4b4b4"),
  flagged: new Color("#b4b4b4"),
  wrongFlag: new Color("#b4b4b4"),
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
  // Open / non-orientable surfaces (cylinder, Möbius strip, Klein bottle) are
  // drawn identically from both sides: flat tiles at the surface (no raised
  // bevel, which would read as a recess from the inside), grout showing in the
  // gaps from either face, and glyphs on whichever side faces the camera.
  readonly twoSided: boolean;
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
    this.twoSided = board.twoSided;

    const basePositions: number[] = [];
    const faceCell: number[] = [];
    let vertexCount = 0;
    // A closed cell is a raised beveled button (3n top-fan + 6n bevel-ring
    // vertices = 3n triangles); a two-sided cell is a flat tile (n triangles).
    const perCell = (n: number) => (this.twoSided ? 3 * n : 9 * n);

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
        count: perCell(n),
        poly,
        centroid,
        normal,
        radius,
        center: centroid,
      });
      vertexCount += perCell(n);
      const triangles = this.twoSided ? n : 3 * n;
      for (let t = 0; t < triangles; t++) faceCell.push(ci);

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
      // open/non-orientable ones draw both faces of their flat tiles, lit and
      // coloured identically (MeshStandardMaterial flips the normal for the
      // back face), so a cell looks and plays the same from either side.
      side: this.twoSided ? DoubleSide : FrontSide,
    });
    const cells = new Mesh(geometry, material);
    cells.name = "cells";
    this.add(cells);

    // Grout under the tile gaps on every board. On closed surfaces it sits
    // below the raised cells; on two-sided surfaces the tiles are flat and
    // coplanar with it, so the grout is pushed back in depth (polygonOffset)
    // and shown from both faces — the gaps read as grout lines, never holes.
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
        side: this.twoSided ? DoubleSide : FrontSide,
        polygonOffset: this.twoSided,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 4,
      }),
    );
    base.name = "base";
    this.add(base);

    const glyphMesh = new Mesh(
      this.glyphGeometry,
      new MeshBasicMaterial({
        map: this.atlas.texture,
        transparent: true,
        alphaTest: 0.4,
        // Billboards drawn over the board, depth-tested so geometry in front of
        // a cell (a nearer wall of a two-sided surface, a nearer bar of a
        // frame) hides its number instead of letting it bleed through; a slight
        // polygon offset keeps a glyph from z-fighting its own tile.
        depthWrite: false,
        depthTest: true,
        polygonOffset: true,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -4,
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
    // Two-sided tiles are flat and static (state shows in colour only); closed
    // cells rise when hidden and sink when revealed, so re-extrude on that flip.
    if (!this.twoSided && isFlat(visual) !== wasFlat) this.writeGeometry(i);
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

  /** (Re)write one cell's geometry: a flat tile at the surface for two-sided
   * boards, else a beveled button — raised for hidden/flagged cells, sunk
   * nearly to the base layer once revealed. */
  private writeGeometry(i: number): void {
    if (this.twoSided) return this.writeFlatTile(i);
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

  /** A flat, slightly-shrunk tile fanned from the cell centroid, sitting on the
   * surface (no raise). It carries the single cell normal and is drawn
   * two-sided, so it reads the same from inside or outside; the grout base
   * behind it shows in the shrink gap as a border line. */
  private writeFlatTile(i: number): void {
    const g = this.geom[i]!;
    const { poly, centroid, normal } = g;
    const n = poly.length;
    const face = poly.map((p) => lerp3(p, centroid, SHRINK));
    g.center = centroid;
    let v = g.start;
    for (let e = 0; e < n; e++) {
      for (const p of [centroid, face[e]!, face[(e + 1) % n]!]) {
        this.positionAttr.setXYZ(v, p[0], p[1], p[2]);
        this.normalAttr.setXYZ(v, normal[0], normal[1], normal[2]);
        v++;
      }
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
      const toCam = normalize([cam[0] - c[0], cam[1] - c[1], cam[2] - c[2]]);
      // On a closed surface only cells whose top face the camera can see carry
      // a glyph, so the far hemisphere's numbers never billboard onto the front
      // (the per-cell camera direction makes the horizon the true perspective
      // silhouette). Two-sided tiles are visible from both faces, so they skip
      // this cull; depth-testing then hides any number a nearer wall occludes.
      if (
        !this.twoSided &&
        toCam[0] * g.normal[0] + toCam[1] * g.normal[1] + toCam[2] * g.normal[2] <=
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
      // Lift the whole billboard toward the camera by its own half-size: a
      // camera-facing quad centred on a tilted cell would otherwise dip behind
      // that cell's face on its far half and be depth-clipped (numbers/flags/
      // mines rendered "in half"). The lift (< a cell width) clears the cell's
      // own face while staying far behind any genuinely nearer wall or frame
      // bar, so occlusion still works.
      const lift = s * 1.3;
      const cx = c[0] + toCam[0] * lift;
      const cy = c[1] + toCam[1] * lift;
      const cz = c[2] + toCam[2] * lift;
      const at = (du: number, dv: number): Vec3 => [
        cx + u[0] * (px + s * du) + v[0] * (py + s * dv),
        cy + u[1] * (px + s * du) + v[1] * (py + s * dv),
        cz + u[2] * (px + s * du) + v[2] * (py + s * dv),
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
