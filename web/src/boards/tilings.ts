// Port of the regular flat lattice builders in minesweeper/boards/tilings.py
// (square / triangle / trigrid / hex / hexhex). Integer lattice points, so
// adjacency uses exact vertex keys — no quantization needed here.
import { buildLattice, cid, type Board, type CellId, type Vertex } from "./core";

const ROOT3 = Math.sqrt(3);

const HEX_VERTEX_OFFSETS: Vertex[] = [
  [0, -2],
  [1, -1],
  [1, 1],
  [0, 2],
  [-1, 1],
  [-1, -1],
];

export function squareBoard(
  rows: number,
  cols: number,
  mineCount: number,
  scale = 32,
): Board {
  const cells = new Map<CellId, Vertex[]>();
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      cells.set(cid(r, c), [
        [c, r],
        [c + 1, r],
        [c + 1, r + 1],
        [c, r + 1],
      ]);
    }
  }
  return buildLattice("square", cells, [scale, scale], mineCount);
}

function triangleVertices(x: number, row: number, up: boolean): Vertex[] {
  // A unit triangle spanning lattice x..x+2 within lattice row `row`.
  if (up) {
    return [
      [x, row + 1],
      [x + 2, row + 1],
      [x + 1, row],
    ];
  }
  return [
    [x, row],
    [x + 2, row],
    [x + 1, row + 1],
  ];
}

export function triangleBoard(size: number, mineCount: number, scale = 52): Board {
  // An equilateral triangle of side `size` split into size^2 unit triangles;
  // row r holds 2r+1 alternating up/down triangles.
  const cells = new Map<CellId, Vertex[]>();
  for (let r = 0; r < size; r++) {
    const xStart = size - r - 1;
    for (let i = 0; i < 2 * r + 1; i++) {
      cells.set(cid(r, i), triangleVertices(xStart + i, r, i % 2 === 0));
    }
  }
  return buildLattice("triangle", cells, [scale / 2, (scale * ROOT3) / 2], mineCount);
}

export function triangleGridBoard(
  rows: number,
  rowWidth: number,
  mineCount: number,
  scale = 52,
): Board {
  const cells = new Map<CellId, Vertex[]>();
  for (let r = 0; r < rows; r++) {
    for (let i = 0; i < rowWidth; i++) {
      cells.set(cid(r, i), triangleVertices(i, r, (r + i) % 2 === 0));
    }
  }
  return buildLattice("trigrid", cells, [scale / 2, (scale * ROOT3) / 2], mineCount);
}

export function hexBoard(
  rows: number,
  cols: number,
  mineCount: number,
  scale = 20,
): Board {
  // Pointy-top hexagons in odd-r offset layout; scale = circumradius.
  const cells = new Map<CellId, Vertex[]>();
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const kx = 2 * c + (r % 2) + 1;
      const ky = 3 * r + 2;
      cells.set(
        cid(r, c),
        HEX_VERTEX_OFFSETS.map(([ox, oy]) => [kx + ox, ky + oy] as Vertex),
      );
    }
  }
  return buildLattice("hex", cells, [(scale * ROOT3) / 2, scale / 2], mineCount);
}

export function hexhexBoard(radius: number, mineCount: number, scale = 20): Board {
  // A big hexagon of small hexagons: all axial (q, r) within `radius`.
  const cells = new Map<CellId, Vertex[]>();
  for (let qq = -radius; qq <= radius; qq++) {
    const rLo = Math.max(-radius, -qq - radius);
    const rHi = Math.min(radius, -qq + radius);
    for (let rr = rLo; rr <= rHi; rr++) {
      const kx = 2 * qq + rr + 2 * radius + 1;
      const ky = 3 * rr + 3 * radius + 2;
      cells.set(
        cid(qq, rr),
        HEX_VERTEX_OFFSETS.map(([ox, oy]) => [kx + ox, ky + oy] as Vertex),
      );
    }
  }
  return buildLattice("hexhex", cells, [(scale * ROOT3) / 2, scale / 2], mineCount);
}
