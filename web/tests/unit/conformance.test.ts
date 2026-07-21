import { describe, expect, it } from "vitest";
import conformance from "@data/conformance.json";
import { DIFFICULTIES } from "../../src/boards/catalog";
import {
  boundaryComponents,
  edgeCount,
  eulerCharacteristic,
  vertexCount,
  type Board,
} from "../../src/boards/core";
import { buildBoard, MODES } from "../../src/boards/presets";

// The board conformance oracle: every ported mode × difficulty must reproduce
// the statistics the Python implementation exported into data/conformance.json,
// so the two implementations cannot drift. Also checks structural invariants
// the oracle does not encode (adjacency symmetry, no self-loops, closure).
const MODE_STATS = conformance.modes as Record<
  string,
  Record<string, {
    cellCount: number;
    mineCount: number;
    euler: number;
    boundaryComponents: number;
    edgeCount: number;
    vertexCount: number;
    hasCellCycle: boolean;
  }>
>;

function checkInvariants(board: Board): void {
  const cells = new Set(board.adjacency.keys());
  for (const [cell, neighbors] of board.adjacency) {
    expect(neighbors).not.toContain(cell); // no self-loops
    for (const n of neighbors) {
      expect(cells.has(n)).toBe(true); // neighbours are on the board
      expect(board.adjacency.get(n)).toContain(cell); // symmetric
    }
  }
}

describe("board conformance oracle", () => {
  it("ported modes match the exported set", () => {
    expect(new Set(MODES)).toEqual(new Set(Object.keys(MODE_STATS)));
  });

  for (const mode of Object.keys(MODE_STATS)) {
    for (const difficulty of DIFFICULTIES) {
      it(`${mode}/${difficulty} matches the oracle`, () => {
        const board = buildBoard(mode, difficulty);
        const want = MODE_STATS[mode]![difficulty]!;
        expect(board.polygons.size).toBe(want.cellCount);
        expect(board.mineCount).toBe(want.mineCount);
        expect(eulerCharacteristic(board)).toBe(want.euler);
        expect(boundaryComponents(board)).toBe(want.boundaryComponents);
        expect(edgeCount(board)).toBe(want.edgeCount);
        expect(vertexCount(board)).toBe(want.vertexCount);
        checkInvariants(board);
      });
    }
  }
});
