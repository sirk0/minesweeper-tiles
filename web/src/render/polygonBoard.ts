import {
  BufferAttribute,
  BufferGeometry,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
} from "three";
import type { Board, CellId, Vertex } from "../boards/core";
import {
  baseColorFor,
  glyphFor,
  type BoardMesh,
  type BoardView,
  type CellAnchor,
  type CellVisual,
} from "./boardMesh";
import { makeGlyphAtlas, type GlyphAtlas } from "./glyphAtlas";

// Renders an arbitrary flat polygon board (square / triangle / hex / ...) as
// one merged beveled geometry: each convex cell becomes a raised top face
// (fan-triangulated) ringed by bevel quads, giving real normals for lighting.
// Per-cell colour is a ranged update; a single glyph-atlas mesh batches the
// number/flag/mine quads. The 3D SolidBoard lays the same construction out on
// a solid's surface.

const SHRINK = 0.04; // pull the whole cell in from shared edges -> visible gaps
const BEVEL = 0.16; // extra inset of the raised top face
const HEIGHT_FRAC = 0.24; // bevel height as a fraction of the cell's "radius"

interface CellGeom {
  start: number; // first vertex index in the position/color buffers
  count: number; // vertex count for this cell
  center: Vertex; // render-space centroid (x, y)
  radius: number; // mean distance centroid -> vertices (glyph sizing)
}

export class PolygonBoard extends Group implements BoardMesh {
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

  constructor(board: Board) {
    super();
    this.atlas = makeGlyphAtlas();
    this.order = [...board.polygons.keys()];
    this.states = this.order.map(() => ({ kind: "hidden" }));
    this.order.forEach((c, i) => this.cellIndex.set(c, i));

    // Centre the board on the origin; flip y so the pixel-space board (y down)
    // renders upright (y up).
    const cx = board.width / 2;
    const cy = board.height / 2;
    this.view = { kind: "flat", width: board.width, height: board.height };

    const positions: number[] = [];
    const faceCell: number[] = [];

    this.order.forEach((cell, ci) => {
      const poly = board.polygons.get(cell)!.map(([x, y]) => [x - cx, cy - y] as Vertex);
      const centroid: Vertex = [
        poly.reduce((s, p) => s + p[0], 0) / poly.length,
        poly.reduce((s, p) => s + p[1], 0) / poly.length,
      ];
      const radius =
        poly.reduce((s, p) => s + Math.hypot(p[0] - centroid[0], p[1] - centroid[1]), 0) /
        poly.length;
      const height = radius * HEIGHT_FRAC;
      const outer = poly.map((p) => lerp(p, centroid, SHRINK));
      const top = poly.map((p) => lerp(p, centroid, SHRINK + BEVEL));
      const n = poly.length;

      const start = positions.length / 3;
      const push = (p: Vertex, z: number) => positions.push(p[0], p[1], z);
      // top face: fan from centroid over the inset polygon
      for (let e = 0; e < n; e++) {
        push(centroid, height);
        push(top[e]!, height);
        push(top[(e + 1) % n]!, height);
        faceCell.push(ci);
      }
      // bevel ring: outer edge (z=0) up to the inset top edge (z=height)
      for (let e = 0; e < n; e++) {
        const a = e;
        const b = (e + 1) % n;
        push(outer[a]!, 0);
        push(outer[b]!, 0);
        push(top[b]!, height);
        push(outer[a]!, 0);
        push(top[b]!, height);
        push(top[a]!, height);
        faceCell.push(ci, ci);
      }
      this.geom.push({
        start,
        count: positions.length / 3 - start,
        center: centroid,
        radius,
      });
    });

    this.faceCell = Int32Array.from(faceCell);
    const posArr = new Float32Array(positions);
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(posArr, 3));
    this.colorAttr = new BufferAttribute(new Float32Array(posArr.length), 3);
    geometry.setAttribute("color", this.colorAttr);
    geometry.computeVertexNormals();

    const cells = new Mesh(
      geometry,
      new MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.65,
        metalness: 0,
        flatShading: true,
        // Cell polygons come from the board builders with per-board winding, so
        // some top faces point away from the camera. DoubleSide keeps them lit
        // and, crucially, raycast-pickable regardless of winding.
        side: DoubleSide,
      }),
    );
    cells.name = "cells";
    this.add(cells);

    const glyphMesh = new Mesh(
      this.glyphGeometry,
      new MeshBasicMaterial({
        map: this.atlas.texture,
        transparent: true,
        alphaTest: 0.4,
        side: DoubleSide,
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
    return { center: [g.center[0], g.center[1], 0], normal: [0, 0, 1] };
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
      const [cxp, cyp] = g.center;
      const s = g.radius * 0.62;
      const z = g.radius * HEIGHT_FRAC + 0.01;
      const [u0, v0, u1, v1] = uv;
      pos.push(
        cxp - s, cyp - s, z, cxp + s, cyp - s, z, cxp + s, cyp + s, z,
        cxp - s, cyp - s, z, cxp + s, cyp + s, z, cxp - s, cyp + s, z,
      );
      uvs.push(u0, v0, u1, v0, u1, v1, u0, v0, u1, v1, u0, v1);
    }
    this.glyphGeometry.setAttribute("position", new BufferAttribute(new Float32Array(pos), 3));
    this.glyphGeometry.setAttribute("uv", new BufferAttribute(new Float32Array(uvs), 2));
    this.glyphGeometry.computeBoundingSphere();
  }
}

function lerp(p: Vertex, q: Vertex, t: number): Vertex {
  return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
}
