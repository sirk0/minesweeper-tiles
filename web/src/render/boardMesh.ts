import { Color, type Group, type Quaternion, type Vector3 } from "three";
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

/** Distance from `center` to the nearest polygon edge (port of gui.py's
 * `inradius`) — how big a glyph fits inside the cell without crossing its
 * edges. Zero/negative means the polygon is degenerate (e.g. seen edge-on). */
export function polygonInradius(
  points: readonly (readonly [number, number])[],
  center: readonly [number, number],
): number {
  let best = Infinity;
  const [px, py] = center;
  for (let i = 0; i < points.length; i++) {
    const [ax, ay] = points[i]!;
    const [bx, by] = points[(i + 1) % points.length]!;
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSq = dx * dx + dy * dy;
    const t =
      lengthSq === 0
        ? 0
        : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSq));
    best = Math.min(best, Math.hypot(px - (ax + t * dx), py - (ay + t * dy)));
  }
  return best;
}

export interface BoardMesh extends Group {
  readonly view: BoardView;
  cellForFace(faceIndex: number): CellId | null;
  cellAnchor(cell: CellId): CellAnchor | null;
  setVisual(cell: CellId, visual: CellVisual): void;
  setHover(cell: CellId | null): void;
  /** Told the current board rotation and camera position so view-dependent
   * content (billboarded glyphs, back-face culling) can follow; meshes
   * without any may omit it. */
  orient?(rotation: Quaternion, cameraWorldPos: Vector3): void;
}
