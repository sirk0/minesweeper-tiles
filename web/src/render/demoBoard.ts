import { BoardMesh, type CellState } from "./boardMesh";
import type { Glyph } from "./glyphAtlas";

// The M0 pipeline-proof board: a hard-coded beveled square grid that exercises
// every renderer path — hidden tiles, all eight number glyphs, a flag and an
// exploded mine — so the smoke e2e/visual test has stable content. Replaced by
// real board graphs from M1 onward.
export function makeDemoBoard(rows = 8, cols = 8): BoardMesh {
  const board = new BoardMesh(rows, cols);
  const revealed = (g: Glyph): CellState => ({ kind: "revealed", glyph: g });

  const plan: Array<[number, CellState]> = [
    [10, revealed(1)],
    [11, revealed(2)],
    [12, revealed(3)],
    [13, revealed(4)],
    [18, revealed(5)],
    [19, revealed(6)],
    [20, revealed(7)],
    [21, revealed(8)],
    [27, revealed(0)],
    [28, revealed(0)],
    [29, revealed(1)],
    [35, { kind: "flag" }],
    [44, { kind: "exploded" }],
    [45, revealed(2)],
    [52, revealed(1)],
  ];
  for (const [cell, state] of plan) {
    if (cell < rows * cols) board.setState(cell, state);
  }
  return board;
}
