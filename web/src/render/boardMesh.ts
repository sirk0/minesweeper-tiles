import { Color, type Group, type Quaternion } from "three";
import type { CellId, Vec3 } from "../boards/core";
import type { Glyph } from "./glyphAtlas";

// Shared vocabulary of the two board meshes (flat PolygonBoard, 3D
// SolidBoard): per-cell visual state, the classic palette, and the interface
// the renderer/session drive. One pipeline — the meshes differ only in how
// the beveled cell geometry is laid out (z=0 plane vs the solid's surface).

export type CellVisual =
  | { kind: "hidden" }
  | { kind: "flagged" }
  | { kind: "revealed"; mines: number }
  | { kind: "mine" }
  | { kind: "exploded" };

// Classic minesweeper gray palette: raised silver tiles, a lighter flat face
// for opened cells, a red exploded cell.
export const COLORS = {
  hidden: new Color("#c6c6c6"),
  revealed: new Color("#dedede"),
  flagged: new Color("#c6c6c6"),
  mine: new Color("#c6c6c6"),
  exploded: new Color("#e05a5a"),
};

export function baseColorFor(visual: CellVisual): Color {
  switch (visual.kind) {
    case "hidden":
      return COLORS.hidden;
    case "flagged":
      return COLORS.flagged;
    case "revealed":
      return COLORS.revealed;
    case "mine":
      return COLORS.mine;
    case "exploded":
      return COLORS.exploded;
  }
}

export function glyphFor(visual: CellVisual): Glyph | null {
  if (visual.kind === "flagged") return "flag";
  if (visual.kind === "mine" || visual.kind === "exploded") return "mine";
  if (visual.kind === "revealed" && visual.mines > 0) {
    return Math.min(visual.mines, 12) as Glyph;
  }
  return null;
}

/** How the renderer should frame the mesh: a flat board is fit into an
 * orthographic frustum by extent; a solid is scaled to the unit sphere and
 * viewed with the perspective camera. */
export type BoardView =
  | { kind: "flat"; width: number; height: number }
  | { kind: "solid"; radius: number };

/** A cell's anchor in mesh-local coordinates: the centre of its (raised) top
 * face and the outward face normal — what picking feedback, glyph placement
 * and the `cellScreenXY` test seam need. */
export interface CellAnchor {
  center: Vec3;
  normal: Vec3;
}

export interface BoardMesh extends Group {
  readonly view: BoardView;
  cellForFace(faceIndex: number): CellId | null;
  cellAnchor(cell: CellId): CellAnchor | null;
  setVisual(cell: CellId, visual: CellVisual): void;
  setHover(cell: CellId | null): void;
  /** Told the current board rotation so view-dependent content (billboarded
   * glyphs) can follow; meshes without any may omit it. */
  orient?(rotation: Quaternion): void;
}
