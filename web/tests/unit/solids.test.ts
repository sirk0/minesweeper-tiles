import { describe, expect, it } from "vitest";
import {
  c80Board,
  cubeBoard,
  cubeFrameBoard,
  snubDodecahedronBoard,
  sphereBoard,
  sphereTriangleBoard,
  steppedBipyramidBoard,
  tetrahedronBoard,
  tetrahedronFrameBoard,
} from "../../src/boards/solids";
import type { Board3D } from "../../src/boards/core";

// Structural invariants of the solids, mirrored from the Python suite
// (tests/test_boards.py) — shape mixes and vertex degrees the conformance
// oracle's aggregate counts don't pin down.

function sizes(board: Board3D): number[] {
  return [...board.polygons.values()].map((p) => p.length).sort((a, b) => a - b);
}

function count(xs: number[], x: number): number {
  return xs.filter((v) => v === x).length;
}

describe("solids", () => {
  it("sphere has sixty pentagons, each with seven neighbors", () => {
    const board = sphereBoard(7);
    expect(board.adjacency.size).toBe(60);
    expect(sizes(board).every((s) => s === 5)).toBe(true);
    for (const n of board.adjacency.values()) expect(n.length).toBe(7);
  });

  it("c80 is a chamfered dodecahedron: 12 pentagons + 30 hexagons", () => {
    const s = sizes(c80Board(5));
    expect(count(s, 5)).toBe(12);
    expect(count(s, 6)).toBe(30);
  });

  it("snub dodecahedron is 12 pentagons + 80 triangles", () => {
    const board = snubDodecahedronBoard(10);
    const s = sizes(board);
    expect(board.adjacency.size).toBe(92);
    expect(count(s, 3)).toBe(80);
    expect(count(s, 5)).toBe(12);
  });

  it("geodesic sphere has 20 * frequency^2 triangles", () => {
    const board = sphereTriangleBoard(10, 2);
    expect(board.polygons.size).toBe(80);
    expect(sizes(board).every((s) => s === 3)).toBe(true);
  });

  it("cube is six n x n square faces", () => {
    for (const n of [2, 4, 6]) {
      const board = cubeBoard(n, 5);
      expect(board.polygons.size).toBe(6 * n * n);
      expect(sizes(board).every((s) => s === 4)).toBe(true);
    }
  });

  it("tetrahedron is four subdivided triangular faces", () => {
    for (const frequency of [1, 4, 6]) {
      const board = tetrahedronBoard(3, frequency);
      expect(board.polygons.size).toBe(4 * frequency * frequency);
      expect(sizes(board).every((s) => s === 3)).toBe(true);
    }
  });

  it("tetrahedron frame is 16 * frequency^2 triangles", () => {
    const board = tetrahedronFrameBoard(8, 2);
    expect(board.polygons.size).toBe(16 * 4);
    expect(sizes(board).every((s) => s === 3)).toBe(true);
  });

  it("polycube surfaces are all quads", () => {
    for (const board of [
      cubeFrameBoard(6, 2, 40),
      steppedBipyramidBoard(6, 3, 20),
    ]) {
      expect(sizes(board).every((s) => s === 4)).toBe(true);
    }
  });

  it("polycube builders validate their arguments", () => {
    expect(() => cubeFrameBoard(4, 2, 5)).toThrow();
    expect(() => steppedBipyramidBoard(4, 1, 5)).toThrow();
  });

  it("solids are closed and one-sided with no cell cycle", () => {
    for (const board of [sphereBoard(7), cubeBoard(4, 12)]) {
      expect(board.twoSided).toBe(false);
      expect(board.cellCycle).toBeNull();
    }
  });
});
