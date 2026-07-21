import {
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
} from "three";
import { makeGlyphAtlas, type Glyph, type GlyphAtlas } from "./glyphAtlas";

// A flat grid of beveled square cells rendered as one merged geometry.
// This is the M0 render-pipeline proof: real bevel geometry (proper normals →
// lighting), per-cell colours driven from cell state, ranged colour updates
// for hover, and a single glyph atlas quad-batched over the cells. Later
// milestones swap the hard-coded square grid for the ported board graphs while
// keeping this rendering approach.

export type CellState =
  | { kind: "hidden" }
  | { kind: "flag" }
  | { kind: "revealed"; glyph: Glyph }
  | { kind: "exploded" };

const HALF = 0.46; // tile half-size (leaves a small gap between tiles)
const BEVEL = 0.1; // horizontal inset of the raised top face
const HEIGHT = 0.16; // bevel height
const TRIS_PER_CELL = 10;
const VERTS_PER_CELL = TRIS_PER_CELL * 3;

const COLORS = {
  hidden: new Color("#b9c0c9"),
  revealed: new Color("#e7e9ee"),
  flag: new Color("#c7ccd4"),
  exploded: new Color("#e5534b"),
};

// Corner offsets (CCW from +z) for a square of the given half-size.
function corners(half: number): Array<[number, number]> {
  return [
    [-half, -half],
    [half, -half],
    [half, half],
    [-half, half],
  ];
}

/** `Group` positioned in the XY plane; cell 0 is top-left, row-major. */
export class BoardMesh extends Group {
  readonly rows: number;
  readonly cols: number;
  readonly cellCount: number;

  private readonly colorAttr: BufferAttribute;
  private readonly geometry: BufferGeometry;
  private readonly glyphMesh: Mesh;
  private readonly glyphGeometry: BufferGeometry;
  private readonly atlas: GlyphAtlas;
  private readonly states: CellState[];
  private hovered = -1;

  constructor(rows: number, cols: number) {
    super();
    this.rows = rows;
    this.cols = cols;
    this.cellCount = rows * cols;
    this.states = Array.from({ length: this.cellCount }, () => ({
      kind: "hidden" as const,
    }));
    this.atlas = makeGlyphAtlas();

    const outer = corners(HALF);
    const inner = corners(HALF - BEVEL);
    const positions = new Float32Array(this.cellCount * VERTS_PER_CELL * 3);
    const colors = new Float32Array(this.cellCount * VERTS_PER_CELL * 3);

    let p = 0;
    const push = (x: number, y: number, z: number): void => {
      positions[p++] = x;
      positions[p++] = y;
      positions[p++] = z;
    };

    for (let c = 0; c < this.cellCount; c++) {
      const [ox, oy] = this.cellCenter(c);
      // top face (two triangles over the inner square, z = HEIGHT)
      const inn = inner.map(([dx, dy]) => [ox + dx, oy + dy] as const);
      const out = outer.map(([dx, dy]) => [ox + dx, oy + dy] as const);
      const t = (i: number, arr: readonly (readonly [number, number])[], z: number) =>
        push(arr[i]![0], arr[i]![1], z);
      t(0, inn, HEIGHT); t(1, inn, HEIGHT); t(2, inn, HEIGHT);
      t(0, inn, HEIGHT); t(2, inn, HEIGHT); t(3, inn, HEIGHT);
      // bevel ring: outer edge (z=0) up to inner edge (z=HEIGHT)
      for (let e = 0; e < 4; e++) {
        const a = e;
        const b = (e + 1) % 4;
        push(out[a]![0], out[a]![1], 0);
        push(out[b]![0], out[b]![1], 0);
        push(inn[b]![0], inn[b]![1], HEIGHT);
        push(out[a]![0], out[a]![1], 0);
        push(inn[b]![0], inn[b]![1], HEIGHT);
        push(inn[a]![0], inn[a]![1], HEIGHT);
      }
    }

    this.geometry = new BufferGeometry();
    this.geometry.setAttribute("position", new BufferAttribute(positions, 3));
    this.colorAttr = new BufferAttribute(colors, 3);
    this.geometry.setAttribute("color", this.colorAttr);
    this.geometry.computeVertexNormals();

    const mesh = new Mesh(
      this.geometry,
      new MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.65,
        metalness: 0.0,
        flatShading: true,
      }),
    );
    mesh.name = "cells";
    this.add(mesh);

    this.glyphGeometry = new BufferGeometry();
    this.glyphMesh = new Mesh(
      this.glyphGeometry,
      new MeshBasicMaterial({
        map: this.atlas.texture,
        transparent: true,
        alphaTest: 0.4,
        side: DoubleSide,
        depthWrite: false,
      }),
    );
    this.glyphMesh.name = "glyphs";
    this.glyphMesh.renderOrder = 1;
    this.add(this.glyphMesh);

    for (let c = 0; c < this.cellCount; c++) this.writeCellColor(c);
    this.rebuildGlyphs();
    this.centerOnOrigin();
  }

  /** World-space centre of a cell (row-major; cell 0 = top-left). */
  cellCenter(cell: number): [number, number] {
    const col = cell % this.cols;
    const row = Math.floor(cell / this.cols);
    return [col, -row];
  }

  /** Triangle (faceIndex) → cell index, for raycast picking. */
  cellForFace(faceIndex: number): number {
    return Math.floor(faceIndex / TRIS_PER_CELL);
  }

  setState(cell: number, state: CellState): void {
    this.states[cell] = state;
    this.writeCellColor(cell);
    this.rebuildGlyphs();
  }

  setHover(cell: number): void {
    if (cell === this.hovered) return;
    const prev = this.hovered;
    this.hovered = cell;
    if (prev >= 0) this.writeCellColor(prev);
    if (cell >= 0) this.writeCellColor(cell);
    this.colorAttr.needsUpdate = true;
  }

  private baseColor(cell: number): Color {
    const s = this.states[cell]!;
    switch (s.kind) {
      case "hidden":
        return COLORS.hidden;
      case "flag":
        return COLORS.flag;
      case "revealed":
        return COLORS.revealed;
      case "exploded":
        return COLORS.exploded;
    }
  }

  private writeCellColor(cell: number): void {
    const col = this.baseColor(cell).clone();
    if (cell === this.hovered) col.offsetHSL(0, 0, 0.08);
    const start = cell * VERTS_PER_CELL;
    for (let i = 0; i < VERTS_PER_CELL; i++) {
      this.colorAttr.setXYZ(start + i, col.r, col.g, col.b);
    }
    this.colorAttr.needsUpdate = true;
  }

  private rebuildGlyphs(): void {
    const quads: number[] = [];
    const uvs: number[] = [];
    const gh = HEIGHT + 0.01;
    const s = HALF - BEVEL - 0.04;
    for (let c = 0; c < this.cellCount; c++) {
      const glyph = this.glyphOf(c);
      if (glyph === null) continue;
      const uv = this.atlas.uv(glyph);
      if (!uv) continue;
      const [cx, cy] = this.cellCenter(c);
      const [u0, v0, u1, v1] = uv;
      // two triangles for the quad
      quads.push(
        cx - s, cy - s, gh, cx + s, cy - s, gh, cx + s, cy + s, gh,
        cx - s, cy - s, gh, cx + s, cy + s, gh, cx - s, cy + s, gh,
      );
      uvs.push(u0, v0, u1, v0, u1, v1, u0, v0, u1, v1, u0, v1);
    }
    this.glyphGeometry.setAttribute(
      "position",
      new BufferAttribute(new Float32Array(quads), 3),
    );
    this.glyphGeometry.setAttribute(
      "uv",
      new BufferAttribute(new Float32Array(uvs), 2),
    );
    this.glyphGeometry.computeBoundingSphere();
  }

  private glyphOf(cell: number): Glyph | null {
    const s = this.states[cell]!;
    if (s.kind === "flag") return "flag";
    if (s.kind === "exploded") return "mine";
    if (s.kind === "revealed") return s.glyph === 0 ? null : s.glyph;
    return null;
  }

  private centerOnOrigin(): void {
    this.position.set(-(this.cols - 1) / 2, (this.rows - 1) / 2, 0);
  }
}
