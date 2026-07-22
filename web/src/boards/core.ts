// Port of minesweeper/boards/core.py (the flat-board parts used by M1).
//
// Python keys cells and vertices by hashable tuples; here a CellId is a
// canonical string built by `cid(...)`, used in Map/Set. Adjacency ordering
// only needs to be deterministic (a string sort), not identical to Python's
// tuple sort — the conformance tests assert invariants, not order.

export type CellId = string;
export type Vertex = [number, number];

export function cid(...parts: (number | string)[]): CellId {
  return parts.join(",");
}

/** Quantize a coordinate to a stable key part (kills -0), matching Python's
 * `round(c, 6)` coincidence used for float-vertex adjacency and topology. */
export function q(c: number): number {
  return Math.round(c * 1e6) / 1e6 || 0;
}

function vkey(x: number, y: number): string {
  return `${q(x)},${q(y)}`;
}

export interface Board {
  mode: string;
  polygons: Map<CellId, Vertex[]>; // pixel-space vertices
  adjacency: Map<CellId, CellId[]>;
  mineCount: number;
  width: number;
  height: number;
}

/** Two cells are neighbours when they share a vertex (exact vertex keys). */
export function sharedVertexAdjacency(
  cells: Map<CellId, string[]>,
): Map<CellId, CellId[]> {
  const byVertex = new Map<string, CellId[]>();
  for (const [cell, verts] of cells) {
    for (const v of verts) {
      let group = byVertex.get(v);
      if (!group) byVertex.set(v, (group = []));
      group.push(cell);
    }
  }
  const touching = new Map<CellId, Set<CellId>>();
  for (const cell of cells.keys()) touching.set(cell, new Set());
  for (const group of byVertex.values()) {
    for (const cell of group) {
      const set = touching.get(cell)!;
      for (const other of group) set.add(other);
    }
  }
  const adjacency = new Map<CellId, CellId[]>();
  for (const [cell, others] of touching) {
    others.delete(cell);
    adjacency.set(cell, [...others].sort());
  }
  return adjacency;
}

/**
 * Assemble a flat board from cells keyed by integer lattice points (matches
 * core.py `_build`): adjacency by shared exact vertices, polygons scaled per
 * axis, size = max extent. `unit` is [ux, uy].
 */
export function buildLattice(
  mode: string,
  latticeCells: Map<CellId, Vertex[]>,
  unit: [number, number],
  mineCount: number,
): Board {
  if (latticeCells.size === 0) throw new Error("board has no cells");
  const keyed = new Map<CellId, string[]>();
  for (const [cell, verts] of latticeCells) {
    keyed.set(
      cell,
      verts.map(([kx, ky]) => `${kx},${ky}`),
    );
  }
  const adjacency = sharedVertexAdjacency(keyed);
  const [ux, uy] = unit;
  const polygons = new Map<CellId, Vertex[]>();
  let width = 0;
  let height = 0;
  for (const [cell, verts] of latticeCells) {
    const poly = verts.map(([kx, ky]) => [kx * ux, ky * uy] as Vertex);
    polygons.set(cell, poly);
    for (const [x, y] of poly) {
      if (x > width) width = x;
      if (y > height) height = y;
    }
  }
  return { mode, polygons, adjacency, mineCount, width, height };
}

// -- topology (surface invariants; shared with the conformance oracle) -------

function edgesOf(board: Board): Map<string, number> {
  const count = new Map<string, number>();
  for (const poly of board.polygons.values()) {
    const pts = poly.map(([x, y]) => vkey(x, y));
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i]!;
      const b = pts[(i + 1) % pts.length]!;
      const edge = a < b ? `${a}|${b}` : `${b}|${a}`;
      count.set(edge, (count.get(edge) ?? 0) + 1);
    }
  }
  return count;
}

/** Distinct polygon corners (V). */
export function vertexCount(board: Board): number {
  const seen = new Set<string>();
  for (const poly of board.polygons.values()) {
    for (const [x, y] of poly) seen.add(vkey(x, y));
  }
  return seen.size;
}

/** V - E + F over the polygon mesh (1 for a flat disc). */
export function eulerCharacteristic(board: Board): number {
  return vertexCount(board) - edgesOf(board).size + board.polygons.size;
}

export function edgeCount(board: Board): number {
  return edgesOf(board).size;
}

/** Number of connected boundary circles (edges belonging to a single cell). */
export function boundaryComponents(board: Board): number {
  const graph = new Map<string, Set<string>>();
  const link = (a: string, b: string) => {
    let s = graph.get(a);
    if (!s) graph.set(a, (s = new Set()));
    s.add(b);
  };
  for (const [edge, n] of edgesOf(board)) {
    if (n !== 1) continue;
    const [a, b] = edge.split("|") as [string, string];
    link(a, b);
    link(b, a);
  }
  const seen = new Set<string>();
  let components = 0;
  for (const start of graph.keys()) {
    if (seen.has(start)) continue;
    components++;
    const stack = [start];
    while (stack.length) {
      const v = stack.pop()!;
      if (seen.has(v)) continue;
      seen.add(v);
      for (const w of graph.get(v) ?? []) if (!seen.has(w)) stack.push(w);
    }
  }
  return components;
}
