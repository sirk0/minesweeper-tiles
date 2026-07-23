// Port of minesweeper/boards/core.py (the flat-board parts used by M1 and,
// since M2, the 3D helpers the solids use).
//
// Python keys cells and vertices by hashable tuples; here a CellId is a
// canonical string built by `cid(...)`, used in Map/Set. Adjacency ordering
// only needs to be deterministic (a string sort), not identical to Python's
// tuple sort — the conformance tests assert invariants, not order.

export type CellId = string;
export type Vertex = [number, number];
export type Vec3 = [number, number, number];

export function cid(...parts: (number | string)[]): CellId {
  return parts.join(",");
}

/** Quantize a coordinate to a stable key part (kills -0), matching Python's
 * `round(c, 6)` coincidence used for float-vertex adjacency and topology. */
export function q(c: number): number {
  return Math.round(c * 1e6) / 1e6 || 0;
}

function vkey(p: readonly number[]): string {
  return p.map(q).join(",");
}

export interface Board {
  mode: string;
  polygons: Map<CellId, Vertex[]>; // pixel-space vertices
  adjacency: Map<CellId, CellId[]>;
  mineCount: number;
  width: number;
  height: number;
}

export interface Board3D {
  mode: string;
  polygons: Map<CellId, Vec3[]>; // vertices on the surface, origin-centered
  adjacency: Map<CellId, CellId[]>;
  mineCount: number;
  radius: number; // max vertex distance from the origin
  twoSided: boolean; // open/non-orientable surfaces show both sides
  // One-step ring translation (a graph automorphism); when set, the UI lets
  // the player scroll the cell contents along it (Klein bottle, M3+).
  cellCycle: Map<CellId, CellId> | null;
}

export type AnyBoard = Board | Board3D;

export function isBoard3D(board: AnyBoard): board is Board3D {
  return "radius" in board;
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

/**
 * Assemble a flat board from cells keyed by float vertex ids and a `positions`
 * map (port of core.py `_finalize_flat`): adjacency by shared exact vertex ids,
 * vertices shifted so the board's bottom-left corner sits at the origin, then
 * scaled uniformly. Shared by the Archimedean window (and, in M5, the aperiodic
 * builders); the lattice builders use `buildLattice` instead.
 */
export function finalizeFlat(
  mode: string,
  cells: Map<CellId, string[]>,
  positions: Map<string, Vertex>,
  mineCount: number,
  scale: number,
): Board {
  if (cells.size === 0) throw new Error("board has no cells");
  const adjacency = sharedVertexAdjacency(cells);
  let minX = Infinity;
  let minY = Infinity;
  for (const keys of cells.values()) {
    for (const k of keys) {
      const p = positions.get(k)!;
      if (p[0] < minX) minX = p[0];
      if (p[1] < minY) minY = p[1];
    }
  }
  const polygons = new Map<CellId, Vertex[]>();
  let width = 0;
  let height = 0;
  for (const [cell, keys] of cells) {
    const poly = keys.map((k) => {
      const p = positions.get(k)!;
      return [(p[0] - minX) * scale, (p[1] - minY) * scale] as Vertex;
    });
    polygons.set(cell, poly);
    for (const [x, y] of poly) {
      if (x > width) width = x;
      if (y > height) height = y;
    }
  }
  return { mode, polygons, adjacency, mineCount, width, height };
}

// -- topology (surface invariants; shared with the conformance oracle) -------

function edgesOf(board: AnyBoard): Map<string, number> {
  const count = new Map<string, number>();
  for (const poly of board.polygons.values()) {
    const pts = poly.map((p: readonly number[]) => vkey(p));
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
export function vertexCount(board: AnyBoard): number {
  const seen = new Set<string>();
  for (const poly of board.polygons.values()) {
    for (const p of poly) seen.add(vkey(p));
  }
  return seen.size;
}

/** V - E + F over the polygon mesh (1 for a flat disc, 2 for a sphere). */
export function eulerCharacteristic(board: AnyBoard): number {
  return vertexCount(board) - edgesOf(board).size + board.polygons.size;
}

export function edgeCount(board: AnyBoard): number {
  return edgesOf(board).size;
}

/** Number of connected boundary circles (edges belonging to a single cell). */
export function boundaryComponents(board: AnyBoard): number {
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

// -- 3D helpers (port of core.py's vector section) ---------------------------

export function normalize(v: Vec3): Vec3 {
  const length = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / length, v[1] / length, v[2] / length];
}

export function cross(a: Vec3, b: Vec3): Vec3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

export function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/** Normal of a (near-)planar 3D polygon, right-hand rule. */
export function newellNormal(points: readonly Vec3[]): Vec3 {
  let nx = 0;
  let ny = 0;
  let nz = 0;
  for (let i = 0; i < points.length; i++) {
    const p = points[i]!;
    const qq = points[(i + 1) % points.length]!;
    nx += (p[1] - qq[1]) * (p[2] + qq[2]);
    ny += (p[2] - qq[2]) * (p[0] + qq[0]);
    nz += (p[0] - qq[0]) * (p[1] + qq[1]);
  }
  return [nx, ny, nz];
}

/** Order vertices counterclockwise as seen from outside the surface. */
export function orientOutward(polygon: Vec3[], outward: Vec3): Vec3[] {
  return dot(newellNormal(polygon), outward) > 0
    ? polygon
    : [...polygon].reverse();
}

/** Order (key, position) pairs by angle around `center` (for points lying
 * roughly on a circle around it, e.g. on a sphere). */
export function tangentOrder<K>(center: Vec3, items: [K, Vec3][]): K[] {
  const n = normalize(center);
  const reference: Vec3 = Math.abs(n[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
  const a = normalize(cross(n, reference));
  const b = cross(n, a);
  const angle = (position: Vec3): number => {
    const d: Vec3 = [
      position[0] - center[0],
      position[1] - center[1],
      position[2] - center[2],
    ];
    return Math.atan2(dot(d, b), dot(d, a));
  };
  return items
    .map(([key, position]) => [key, angle(position)] as const)
    .sort((x, y) => x[1] - y[1])
    .map(([key]) => key);
}
