import {
  BufferAttribute,
  BufferGeometry,
  DoubleSide,
  FrontSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
} from "three";
import {
  cross,
  newellNormal,
  normalize,
  type Board3D,
  type CellId,
  type Vec3,
} from "../boards/core";
import {
  baseColorFor,
  glyphFor,
  type BoardMesh,
  type BoardView,
  type CellAnchor,
  type CellVisual,
} from "./boardMesh";
import { makeGlyphAtlas, type GlyphAtlas } from "./glyphAtlas";

// The 3D counterpart of PolygonBoard: a Board3D's outward-wound surface
// polygons become one merged beveled geometry — each cell an inset top face
// raised along its outward normal, ringed by bevel quads. Closed surfaces
// cull back faces (the classic sphere/cube look); open or non-orientable
// surfaces (M3's cylinder / Möbius strip / Klein bottle) render DoubleSide
// with the back side dimmed in the shader, staying opaque so the depth buffer
// resolves self-intersections. Glyphs are stickers in each cell's plane,
// kept upright relative to the world y-axis.

const SHRINK = 0.04;
const BEVEL = 0.16;
// Lower relief than the flat renderer's 0.24: on a closed surface the cells
// tilt against each other, and tall plateaus on big curved cells (the
// sphere's pentagons) shingle over their neighbours at the silhouette.
const HEIGHT_FRAC = 0.1;
const BACK_DIM = 0.82; // matches the pygame two-sided back-face dimming
const BASE_COLOR = "#8e8e8e"; // grout surface showing through the tile gaps

interface CellGeom {
  start: number;
  count: number;
  center: Vec3; // centre of the raised top face
  normal: Vec3; // outward unit normal
  radius: number; // mean distance centroid -> vertices
}

export class SolidBoard extends Group implements BoardMesh {
  readonly view: BoardView;
  private readonly order: CellId[];
  private readonly cellIndex = new Map<CellId, number>();
  private readonly geom: CellGeom[] = [];
  private readonly faceCell: Int32Array;
  private readonly colorAttr: BufferAttribute;
  private readonly glyphGeometry = new BufferGeometry();
  private readonly atlas: GlyphAtlas;
  private readonly states: CellVisual[];
  private hovered = -1;

  constructor(board: Board3D) {
    super();
    this.atlas = makeGlyphAtlas();
    this.order = [...board.polygons.keys()];
    this.states = this.order.map(() => ({ kind: "hidden" }));
    this.order.forEach((c, i) => this.cellIndex.set(c, i));
    this.view = { kind: "solid", radius: board.radius };

    const positions: number[] = [];
    const normals: number[] = [];
    const faceCell: number[] = [];
    const basePositions: number[] = [];

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
      const height = radius * HEIGHT_FRAC;
      const lift: Vec3 = [
        normal[0] * height,
        normal[1] * height,
        normal[2] * height,
      ];
      const outer = poly.map((p) => lerp3(p, centroid, SHRINK));
      const top = poly.map((p) => add3(lerp3(p, centroid, SHRINK + BEVEL), lift));
      const topCenter = add3(centroid, lift);

      // Opaque base layer under the whole (unshrunk) polygon: the tile gaps
      // and the silhouette show this grout surface instead of seeing through
      // the hollow interior.
      for (let e = 0; e < n; e++) {
        for (const p of [centroid, poly[e]!, poly[(e + 1) % n]!]) {
          basePositions.push(p[0], p[1], p[2]);
        }
      }

      const start = positions.length / 3;
      const push = (p: Vec3, nrm: Vec3) => {
        positions.push(p[0], p[1], p[2]);
        normals.push(nrm[0], nrm[1], nrm[2]);
      };
      // top face: fan from the raised centroid (outward winding preserved —
      // the board's polygons are counterclockwise seen from outside). The
      // whole fan carries the cell normal, so a cell on a curved surface
      // (whose polygon is not planar — e.g. the sphere's pentagons) still
      // shades as one clean facet instead of a pinwheel of fan triangles.
      for (let e = 0; e < n; e++) {
        push(topCenter, normal);
        push(top[e]!, normal);
        push(top[(e + 1) % n]!, normal);
        faceCell.push(ci);
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
        push(outer[a]!, quadNormal);
        push(outer[b]!, quadNormal);
        push(top[b]!, quadNormal);
        push(outer[a]!, quadNormal);
        push(top[b]!, quadNormal);
        push(top[a]!, quadNormal);
        faceCell.push(ci, ci);
      }
      this.geom.push({
        start,
        count: positions.length / 3 - start,
        center: topCenter,
        normal,
        radius,
      });
    });

    this.faceCell = Int32Array.from(faceCell);
    const posArr = new Float32Array(positions);
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(posArr, 3));
    geometry.setAttribute("normal", new BufferAttribute(new Float32Array(normals), 3));
    this.colorAttr = new BufferAttribute(new Float32Array(posArr.length), 3);
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
        // Glyph quads share their cell's winding, so back-face culling hides
        // them exactly when their cell is culled.
        side: board.twoSided ? DoubleSide : FrontSide,
        depthWrite: false,
      }),
    );
    glyphMesh.name = "glyphs";
    glyphMesh.renderOrder = 1;
    this.add(glyphMesh);

    for (let i = 0; i < this.order.length; i++) this.writeColor(i);
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
    this.states[i] = visual;
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

  private writeColor(i: number): void {
    const col = baseColorFor(this.states[i]!).clone();
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
    for (let i = 0; i < this.order.length; i++) {
      const glyph = glyphFor(this.states[i]!);
      if (glyph === null) continue;
      const uv = this.atlas.uv(glyph);
      if (!uv) continue;
      const g = this.geom[i]!;
      const { u, v } = glyphBasis(g.normal);
      const s = g.radius * 0.62;
      // float the sticker just off the top face to avoid z-fighting
      const c = add3(g.center, [
        g.normal[0] * g.radius * 0.06,
        g.normal[1] * g.radius * 0.06,
        g.normal[2] * g.radius * 0.06,
      ]);
      const at = (du: number, dv: number): Vec3 => [
        c[0] + u[0] * s * du + v[0] * s * dv,
        c[1] + u[1] * s * du + v[1] * s * dv,
        c[2] + u[2] * s * du + v[2] * s * dv,
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

/** An in-plane basis for a cell's glyph sticker: `v` (text-up) is the world
 * y-axis projected into the face plane, so digits read upright in the
 * board's rest orientation; near the poles fall back to the z-axis. `u` is
 * text-right for a viewer looking at the face from outside. */
function glyphBasis(n: Vec3): { u: Vec3; v: Vec3 } {
  let ref: Vec3 = [0, 1, 0];
  if (Math.abs(n[1]) > 0.99) ref = n[1] > 0 ? [0, 0, -1] : [0, 0, 1];
  const d = ref[0] * n[0] + ref[1] * n[1] + ref[2] * n[2];
  const v = normalize([
    ref[0] - d * n[0],
    ref[1] - d * n[1],
    ref[2] - d * n[2],
  ]);
  return { u: cross(v, n), v };
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
