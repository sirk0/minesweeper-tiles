import { describe, expect, it } from "vitest";
import {
  cylinderBoard,
  cylinderHexBoard,
  cylinderTriangleBoard,
  kleinBoard,
  kleinHexBoard,
  kleinTriangleBoard,
  mobiusBoard,
  mobiusHexBoard,
  torusBoard,
  torusHexBoard,
} from "../../src/boards/surfaces";
import type { Board3D, CellId } from "../../src/boards/core";

// Structural invariants of the wrapped surfaces, mirrored from the Python suite
// (tests/test_boards.py TestKleinBottle / TestKleinTilings and the wrap
// invariants) — neighbour degrees, two-sidedness, and the cell-cycle graph
// automorphism the conformance oracle's aggregate counts don't pin down.

function degrees(board: Board3D): Set<number> {
  return new Set([...board.adjacency.values()].map((n) => n.length));
}

/** A cell_cycle is a bijective adjacency-preserving permutation of the cells:
 * neighbours map to neighbours, so the board reads correctly at every scroll
 * offset. */
function assertScrollCycle(board: Board3D): void {
  const cycle = board.cellCycle;
  expect(cycle).not.toBeNull();
  const cyc = cycle!;
  expect(new Set(cyc.keys())).toEqual(new Set(board.adjacency.keys()));
  expect(new Set(cyc.values()).size).toBe(cyc.size); // a bijection
  for (const [cell, neighbors] of board.adjacency) {
    const shifted = new Set(board.adjacency.get(cyc.get(cell)!)!);
    for (const n of neighbors) expect(shifted.has(cyc.get(n)!)).toBe(true);
  }
}

/** The order of the cell cycle: how many steps return a cell to itself. */
function cycleOrder(cycle: Map<CellId, CellId>): number {
  const start = cycle.keys().next().value as CellId;
  let cur = cycle.get(start)!;
  let order = 1;
  while (cur !== start) {
    cur = cycle.get(cur)!;
    order++;
  }
  return order;
}

describe("wrapped surfaces", () => {
  it("torus quads all have eight neighbours, closed and one-sided", () => {
    const board = torusBoard(12, 6, 9);
    expect(degrees(board)).toEqual(new Set([8]));
    expect(board.twoSided).toBe(false);
    expect(board.cellCycle).toBeNull();
  });

  it("torus of hexagons is borderless with six neighbours each", () => {
    const board = torusHexBoard(6, 12, 9);
    expect(degrees(board)).toEqual(new Set([6]));
    expect(board.twoSided).toBe(false);
  });

  it("cylinder and Möbius are two-sided with no scroll cycle", () => {
    for (const board of [cylinderBoard(12, 7, 10), mobiusBoard(20, 4, 10)]) {
      expect(board.twoSided).toBe(true);
      expect(board.cellCycle).toBeNull();
    }
  });

  it("klein square is a closed non-orientable surface, 8 neighbours each", () => {
    const board = kleinBoard(12, 6, 9);
    expect(degrees(board)).toEqual(new Set([8]));
    expect(board.twoSided).toBe(true);
  });

  it("klein carries a ring-translation graph automorphism", () => {
    assertScrollCycle(kleinBoard(12, 6, 9));
    assertScrollCycle(kleinBoard(16, 8, 20));
  });

  it("klein cell cycle has period twice the ring (seam flips the tube)", () => {
    // crossing the seam flips the tube, so a cell returns only after two loops
    expect(cycleOrder(kleinBoard(12, 6, 9).cellCycle!)).toBe(24);
  });

  it("klein triangle/hex cell counts match Python", () => {
    expect(kleinTriangleBoard(12, 6, 14).adjacency.size).toBe(144);
    expect(kleinHexBoard(6, 4, 9).adjacency.size).toBe(24);
  });

  it("klein hexagons carry a scroll cycle", () => {
    assertScrollCycle(kleinHexBoard(8, 6, 20));
  });

  it("klein triangles scroll only when tube is two mod four", () => {
    assertScrollCycle(kleinTriangleBoard(12, 6, 14)); // 6 ≡ 2 (mod 4)
    expect(kleinTriangleBoard(12, 8, 14).cellCycle).toBeNull(); // 8 ≡ 0
  });

  it("wrap builders validate their seam arguments", () => {
    expect(() => kleinBoard(12, 5, 9)).toThrow(); // tube must be even
    expect(() => kleinTriangleBoard(10, 5, 12)).toThrow(); // tube must be even
    expect(() => kleinHexBoard(6, 5, 9)).toThrow(); // rows must be even
    expect(() => torusHexBoard(5, 12, 9)).toThrow(); // rows must be even
    expect(() => mobiusHexBoard(14, 4, 6)).toThrow(); // rows must be odd
    expect(() => cylinderTriangleBoard(15, 6, 11)).toThrow(); // ring must be even
    expect(() => cylinderHexBoard(12, 6, 9)).not.toThrow();
  });
});
