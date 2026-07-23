// Port of minesweeper/boards/surfaces.py — wrapping the regular flat tilings
// (square / triangle / hexagon) onto 3D surfaces (torus, cylinder, Möbius
// strip, Klein bottle). M3 ports the twelve regular-tiling wraps; the
// Archimedean `arch_*` wraps land with the template engine in M4.
//
// Each wrapped board is built the same way: pick vertex keys on an integer
// grid, glue them at the seam, map each key onto the surface with an immersion
// (torusPoint / cylinderPoint / mobiusPoint / kleinPoint), then hand the cells
// to `assemble`, which shares the adjacency / polygon / Board3D tail and the
// outward-orientation (closed) vs two-sided (open/non-orientable) choice.
//
// Adjacency keys on the *symbolic* (integer) vertex ids, exactly as Python's
// `_shared_vertex_adjacency` does, not on floating-point positions — two cells
// are neighbours iff they share a glued vertex id. Positions are a pure
// function of the canonical (post-glue) vertex id, so a shared id always maps
// to one point and the seam closes.
import {
  cid,
  orientOutward,
  sharedVertexAdjacency,
  type Board3D,
  type CellId,
  type Vec3,
} from "./core";

const TWO_PI = 2 * Math.PI;
const ROOT3 = Math.sqrt(3);

// Pointy-top hex vertex offsets on the integer lattice (shared with tilings).
const HEX_VERTEX_OFFSETS: [number, number][] = [
  [0, -2],
  [1, -1],
  [1, 1],
  [0, 2],
  [-1, 1],
  [-1, -1],
];

/** A unit triangle spanning lattice x..x+2 within lattice row `row` (port of
 * tilings.py `_triangle_vertices`; the x unit is half a side, y the height). */
function triangleVertices(x: number, row: number, up: boolean): [number, number][] {
  return up
    ? [
        [x, row + 1],
        [x + 2, row + 1],
        [x + 1, row],
      ]
    : [
        [x, row],
        [x + 2, row],
        [x + 1, row + 1],
      ];
}

// -- immersions: one point of a surface from its parameters ------------------

/** A donut point at angle `theta` round the ring and `phi` round the tube. */
function torusPoint(theta: number, phi: number, tubeRadius: number): Vec3 {
  const radial = 1 + tubeRadius * Math.cos(phi);
  return [radial * Math.cos(theta), radial * Math.sin(theta), tubeRadius * Math.sin(phi)];
}

/** A unit-radius cylinder point at angle `theta` round the axis, `height` up. */
function cylinderPoint(theta: number, height: number): Vec3 {
  return [Math.cos(theta), height, Math.sin(theta)];
}

/** A Möbius-strip point: `u` the angle round the loop, `v` the signed offset
 * across the half-twisting band. */
function mobiusPoint(u: number, v: number): Vec3 {
  const radial = 1 + v * Math.cos(u / 2);
  return [radial * Math.cos(u), radial * Math.sin(u), v * Math.sin(u / 2)];
}

/** A point on the classic self-intersecting Klein *bottle*. `u` runs the
 * profile round the ring (up the body, over the top, down and through the
 * neck), `v` round the circular cross-section; `tube` scales the thickness.
 * Returned in the parametrization's own frame; the wrap builders recentre it. */
function kleinPoint(u: number, v: number, tube = 1): Vec3 {
  const cu = Math.cos(u);
  const su = Math.sin(u);
  const cv = Math.cos(v);
  const r = tube * (2.5 - 1.5 * cu); // thin at the neck, fat at the belly
  let x: number;
  let y: number;
  if (u < Math.PI) {
    // body: the tube is swept around the profile
    x = 3 * cu * (1 + su) + r * cu * cv;
    y = 8 * su + r * su * cv;
  } else {
    // neck: a straight tube diving through the body
    x = 3 * cu * (1 + su) - r * cv;
    y = 8 * su;
  }
  return [x, y, r * Math.sin(v)];
}

// -- assembly: shared tail for every wrapped board ---------------------------

type Positions = Map<string, Vec3>;
type Cells = Map<CellId, string[]>;

function centroidOf(points: readonly Vec3[]): Vec3 {
  const c: Vec3 = [0, 0, 0];
  for (const p of points) {
    c[0] += p[0];
    c[1] += p[1];
    c[2] += p[2];
  }
  return [c[0] / points.length, c[1] / points.length, c[2] / points.length];
}

/** Wind a polygon outward, away from the ring circle through the tube centre
 * (the outside of a closed torus). */
function orientFromRing(polygon: Vec3[]): Vec3[] {
  const centroid = centroidOf(polygon);
  const ringScale = Math.hypot(centroid[0], centroid[1]) || 1;
  const ringPoint: Vec3 = [centroid[0] / ringScale, centroid[1] / ringScale, 0];
  const outward: Vec3 = [
    centroid[0] - ringPoint[0],
    centroid[1] - ringPoint[1],
    centroid[2] - ringPoint[2],
  ];
  return orientOutward(polygon, outward);
}

function maxRadius(positions: Positions): number {
  let r = 0;
  for (const p of positions.values()) r = Math.max(r, Math.hypot(p[0], p[1], p[2]));
  return r;
}

/** Shift every position so their centroid sits at the origin (the bottle
 * immersion is not origin-centred; the 3D view frames and pivots about the
 * origin). Mutates and returns `positions`. */
function kleinRecentre(positions: Positions): Positions {
  const c = centroidOf([...positions.values()]);
  for (const [k, p] of positions) positions.set(k, [p[0] - c[0], p[1] - c[1], p[2] - c[2]]);
  return positions;
}

interface AssembleOpts {
  twoSided: boolean;
  radius: number | ((positions: Positions) => number);
  cellCycle?: Map<CellId, CellId> | null;
}

/** Build adjacency and polygons and wrap them in a Board3D. Closed surfaces
 * (`twoSided` false) orient each face outward from the ring; open or
 * non-orientable ones keep both sides. */
function assemble(
  mode: string,
  cells: Cells,
  positions: Positions,
  mineCount: number,
  { twoSided, radius, cellCycle = null }: AssembleOpts,
): Board3D {
  const adjacency = sharedVertexAdjacency(cells);
  const polygons = new Map<CellId, Vec3[]>();
  for (const [cell, keys] of cells) {
    const poly = keys.map((k) => positions.get(k)!);
    polygons.set(cell, twoSided ? poly : orientFromRing(poly));
  }
  const r = typeof radius === "function" ? radius(positions) : radius;
  return { mode, polygons, adjacency, mineCount, radius: r, twoSided, cellCycle };
}

// -- the donut ---------------------------------------------------------------

/** A donut tiled with `ring * tube` quadrilaterals, wrapping in both
 * directions, so every cell has exactly 8 neighbours. */
export function torusBoard(
  ring: number,
  tube: number,
  mineCount: number,
  tubeRadius = 0.45,
): Board3D {
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (i: number, j: number): string => {
    const k = `${i},${j}`;
    if (!positions.has(k)) {
      positions.set(k, torusPoint(TWO_PI * i / ring, TWO_PI * j / tube, tubeRadius));
    }
    return k;
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < tube; j++) {
      cells.set(cid(i, j), [
        put(i, j),
        put((i + 1) % ring, j),
        put((i + 1) % ring, (j + 1) % tube),
        put(i, (j + 1) % tube),
      ]);
    }
  }
  return assemble("torus", cells, positions, mineCount, {
    twoSided: false,
    radius: 1 + tubeRadius,
  });
}

/** A donut tiled with triangles: each quad of the torus grid split along a
 * diagonal, giving `2 * ring * tube` cells. */
export function torusTriangleBoard(
  ring: number,
  tube: number,
  mineCount: number,
  tubeRadius = 0.45,
): Board3D {
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (i: number, j: number): string => {
    const k = `${i},${j}`;
    if (!positions.has(k)) {
      positions.set(k, torusPoint(TWO_PI * i / ring, TWO_PI * j / tube, tubeRadius));
    }
    return k;
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < tube; j++) {
      const a = put(i, j);
      const b = put((i + 1) % ring, j);
      const c = put((i + 1) % ring, (j + 1) % tube);
      const d = put(i, (j + 1) % tube);
      cells.set(cid(i, j, 0), [a, b, c]);
      cells.set(cid(i, j, 1), [a, c, d]);
    }
  }
  return assemble("torustri", cells, positions, mineCount, {
    twoSided: false,
    radius: 1 + tubeRadius,
  });
}

/** A donut tiled entirely with hexagons (the torus has Euler characteristic
 * 0). The lattice wraps round the tube (`rows`, must be even) and the ring
 * (`cols`); every cell has 6 neighbours. */
export function torusHexBoard(
  rows: number,
  cols: number,
  mineCount: number,
  tubeRadius = 0.45,
): Board3D {
  if (rows % 2) throw new Error("rows must be even so the offset lattice wraps");
  const kxPeriod = 2 * cols;
  const kyPeriod = 3 * rows;
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (kx: number, ky: number): string => {
    const k = `${kx},${ky}`;
    if (!positions.has(k)) {
      positions.set(k, torusPoint(TWO_PI * kx / kxPeriod, TWO_PI * ky / kyPeriod, tubeRadius));
    }
    return k;
  };
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const kx = 2 * c + (r % 2) + 1;
      const ky = 3 * r + 2;
      cells.set(
        cid(r, c),
        HEX_VERTEX_OFFSETS.map(([ox, oy]) =>
          put((kx + ox + kxPeriod) % kxPeriod, (ky + oy + kyPeriod) % kyPeriod),
        ),
      );
    }
  }
  return assemble("torushex", cells, positions, mineCount, {
    twoSided: false,
    radius: 1 + tubeRadius,
  });
}

// -- the Möbius strip --------------------------------------------------------

/** A Möbius strip tiled with quadrilaterals: `ring` segments around,
 * `widthCells` across. After a full loop the strip flips, so column `ring`
 * glues to column 0 upside down. */
export function mobiusBoard(ring: number, widthCells: number, mineCount: number): Board3D {
  const halfWidth = Math.min(0.7, (Math.PI * widthCells) / ring / 2);
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const key = (i: number, j: number): [number, number] =>
    i >= ring ? [i - ring, widthCells - j] : [i, j];
  const put = (i: number, j: number): string => {
    const [ci, cj] = key(i, j);
    const k = `${ci},${cj}`;
    if (!positions.has(k)) {
      positions.set(k, mobiusPoint(TWO_PI * ci / ring, halfWidth * (2 * cj / widthCells - 1)));
    }
    return k;
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < widthCells; j++) {
      cells.set(cid(i, j), [put(i, j), put(i + 1, j), put(i + 1, j + 1), put(i, j + 1)]);
    }
  }
  return assemble("mobius", cells, positions, mineCount, {
    twoSided: true,
    radius: 1 + halfWidth,
  });
}

/** A Möbius strip tiled with triangles: each quad split along a diagonal. */
export function mobiusTriangleBoard(
  ring: number,
  widthCells: number,
  mineCount: number,
): Board3D {
  const halfWidth = Math.min(0.7, (Math.PI * widthCells) / ring / 2);
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const key = (i: number, j: number): [number, number] =>
    i >= ring ? [i - ring, widthCells - j] : [i, j];
  const put = (i: number, j: number): string => {
    const [ci, cj] = key(i, j);
    const k = `${ci},${cj}`;
    if (!positions.has(k)) {
      positions.set(k, mobiusPoint(TWO_PI * ci / ring, halfWidth * (2 * cj / widthCells - 1)));
    }
    return k;
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < widthCells; j++) {
      const a = put(i, j);
      const b = put(i + 1, j);
      const c = put(i + 1, j + 1);
      const d = put(i, j + 1);
      cells.set(cid(i, j, 0), [a, b, c]);
      cells.set(cid(i, j, 1), [a, c, d]);
    }
  }
  return assemble("mobiustri", cells, positions, mineCount, {
    twoSided: true,
    radius: 1 + halfWidth,
  });
}

/** A Möbius strip tiled with hexagons: `ring` columns of `rows` hexagons
 * glued end-to-start with a vertical flip. `rows` must be odd. */
export function mobiusHexBoard(ring: number, rows: number, mineCount: number): Board3D {
  if (rows % 2 === 0) throw new Error("rows must be odd so the lattice survives the flip");
  const kxPeriod = 2 * ring;
  const kyTop = 3 * rows + 1;
  const halfWidth = Math.min(0.7, (Math.PI * rows) / ring);
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const key = (kx: number, ky: number): [number, number] =>
    kx >= kxPeriod ? [kx - kxPeriod, kyTop - ky] : [kx, ky];
  const put = (kx: number, ky: number): string => {
    const [ckx, cky] = key(kx, ky);
    const k = `${ckx},${cky}`;
    if (!positions.has(k)) {
      positions.set(k, mobiusPoint(TWO_PI * ckx / kxPeriod, halfWidth * (2 * cky / kyTop - 1)));
    }
    return k;
  };
  for (let c = 0; c < ring; c++) {
    for (let r = 0; r < rows; r++) {
      const kx = 2 * c + (r % 2) + 1;
      const ky = 3 * r + 2;
      cells.set(
        cid(r, c),
        HEX_VERTEX_OFFSETS.map(([ox, oy]) => put(kx + ox, ky + oy)),
      );
    }
  }
  return assemble("mobiushex", cells, positions, mineCount, {
    twoSided: true,
    radius: 1 + halfWidth,
  });
}

// -- the Klein bottle --------------------------------------------------------

/** Sorted, joined vertex-key set — a frozenset stand-in for matching a cell to
 * its ring-shifted image. */
function vertexSetKey(keys: string[]): string {
  return [...keys].sort().join(";");
}

/** A Klein bottle tiled with `ring * tube` quadrilaterals, shaped as the
 * classic self-intersecting bottle. The cross-section (`tube`, must be even)
 * wraps straight; after a full loop round the ring the tube seam glues flipped
 * (`j -> tube/2 - j - 1`), so the surface is closed yet non-orientable. Carries
 * a `cellCycle` — the one-step ring translation — so the UI can scroll cell
 * contents past the self-intersection. */
export function kleinBoard(
  ring: number,
  tube: number,
  mineCount: number,
  tubeScale = 1,
): Board3D {
  if (tube % 2) throw new Error("tube must be even so the seam reflection lands on cells");
  const half = tube / 2;
  const key = (i: number, j: number): [number, number] =>
    i >= ring
      ? [i - ring, ((half - j - 1) % tube + tube) % tube]
      : [i, ((j % tube) + tube) % tube];
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (i: number, j: number): string => {
    const [ci, cj] = key(i, j);
    const k = `${ci},${cj}`;
    if (!positions.has(k)) {
      // half-cell offset in v keeps every vertex off the self-intersection
      // circle (v = 0, π), so no two distinct vertices coincide
      positions.set(k, kleinPoint(TWO_PI * ci / ring, (TWO_PI * (cj + 0.5)) / tube, tubeScale));
    }
    return k;
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < tube; j++) {
      cells.set(cid(i, j), [put(i, j), put(i + 1, j), put(i + 1, j + 1), put(i, j + 1)]);
    }
  }
  kleinRecentre(positions);

  // one step forward along the ring. A cell is indexed by its low-j corner, so
  // at the seam the reflection maps [j, j+1] to [tube/2-j-2, tube/2-j-1] — the
  // cell flip is one below the vertex flip used in key().
  const cellCycle = new Map<CellId, CellId>();
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < tube; j++) {
      const to =
        i + 1 >= ring ? cid(0, ((half - j - 2) % tube + tube) % tube) : cid(i + 1, j);
      cellCycle.set(cid(i, j), to);
    }
  }
  return assemble("klein", cells, positions, mineCount, {
    twoSided: true,
    radius: maxRadius,
    cellCycle,
  });
}

/** A Klein bottle tiled with triangles: each quad of the `ring * tube` bottle
 * grid split along a diagonal. The diagonal alternates by column so the seam's
 * glide carries diagonals to diagonals: when `tube ≡ 2 (mod 4)` the ring
 * translation is an automorphism and the board scrolls; otherwise `cellCycle`
 * is left null. */
export function kleinTriangleBoard(
  ring: number,
  tube: number,
  mineCount: number,
  tubeScale = 1,
): Board3D {
  if (tube % 2) throw new Error("tube must be even so the seam reflection lands on cells");
  const half = tube / 2;
  const key = (i: number, j: number): [number, number] =>
    i >= ring
      ? [i - ring, ((half - j - 1) % tube + tube) % tube]
      : [((i % ring) + ring) % ring, ((j % tube) + tube) % tube];
  const cells: Cells = new Map();
  const cellVerts = new Map<CellId, [number, number][]>();
  const positions: Positions = new Map();
  const put = (i: number, j: number): [string, [number, number]] => {
    const canon = key(i, j);
    const k = `${canon[0]},${canon[1]}`;
    if (!positions.has(k)) {
      positions.set(
        k,
        kleinPoint(TWO_PI * canon[0] / ring, (TWO_PI * (canon[1] + 0.5)) / tube, tubeScale),
      );
    }
    return [k, canon];
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < tube; j++) {
      const [ak, av] = put(i, j);
      const [bk, bv] = put(i + 1, j);
      const [ck, cv] = put(i + 1, j + 1);
      const [dk, dv] = put(i, j + 1);
      if (j % 2 === 0) {
        // "/" diagonal a--c
        cells.set(cid(i, j, 0), [ak, bk, ck]);
        cellVerts.set(cid(i, j, 0), [av, bv, cv]);
        cells.set(cid(i, j, 1), [ak, ck, dk]);
        cellVerts.set(cid(i, j, 1), [av, cv, dv]);
      } else {
        // "\" diagonal b--d
        cells.set(cid(i, j, 0), [ak, bk, dk]);
        cellVerts.set(cid(i, j, 0), [av, bv, dv]);
        cells.set(cid(i, j, 1), [bk, ck, dk]);
        cellVerts.set(cid(i, j, 1), [bv, cv, dv]);
      }
    }
  }
  kleinRecentre(positions);

  // one step forward along the ring, matched by vertex set; kept only if it is
  // a bijection over the cells (a graph automorphism), else no scroll
  const cellCycle = ringCycleByVertexSet(cells, cellVerts, key);
  return assemble("kleintri", cells, positions, mineCount, {
    twoSided: true,
    radius: maxRadius,
    cellCycle,
  });
}

/** A Klein bottle tiled entirely with hexagons: `ring` columns around the
 * loop, `rows` (must be even) hexagons around the tube. The tube wraps
 * straight; the ring seam glues the tube reflected (`ky -> 4 - ky`). */
export function kleinHexBoard(
  ring: number,
  rows: number,
  mineCount: number,
  tubeScale = 1,
): Board3D {
  if (rows % 2) throw new Error("rows must be even so the tube lattice wraps");
  const kxPeriod = 2 * ring;
  const kyPeriod = 3 * rows;
  const key = (kx: number, ky: number): [number, number] =>
    kx >= kxPeriod
      ? [((kx - kxPeriod) % kxPeriod + kxPeriod) % kxPeriod, ((4 - ky) % kyPeriod + kyPeriod) % kyPeriod]
      : [((kx % kxPeriod) + kxPeriod) % kxPeriod, ((ky % kyPeriod) + kyPeriod) % kyPeriod];
  const cells: Cells = new Map();
  const cellVerts = new Map<CellId, [number, number][]>();
  const positions: Positions = new Map();
  const put = (kx: number, ky: number): [string, [number, number]] => {
    const canon = key(kx, ky);
    const k = `${canon[0]},${canon[1]}`;
    if (!positions.has(k)) {
      // centre v on ky = 2 (the seam mirror axis) and offset by π/2 so the
      // immersion's seam reflection matches the ky -> 4 - ky lattice flip
      positions.set(
        k,
        kleinPoint(
          TWO_PI * canon[0] / kxPeriod,
          (TWO_PI * (canon[1] - 2)) / kyPeriod + Math.PI / 2,
          tubeScale,
        ),
      );
    }
    return [k, canon];
  };
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < ring; c++) {
      const kx = 2 * c + (r % 2) + 1;
      const ky = 3 * r + 2;
      const keys: string[] = [];
      const verts: [number, number][] = [];
      for (const [ox, oy] of HEX_VERTEX_OFFSETS) {
        const [k, canon] = put(kx + ox, ky + oy);
        keys.push(k);
        verts.push(canon);
      }
      cells.set(cid(r, c), keys);
      cellVerts.set(cid(r, c), verts);
    }
  }
  kleinRecentre(positions);

  // one column forward along the ring (kx += 2), matched by vertex set (an
  // automorphism up to the seam's tube flip)
  const cellCycle = ringCycleByVertexSet(cells, cellVerts, key, 2);
  return assemble("kleinhex", cells, positions, mineCount, {
    twoSided: true,
    radius: maxRadius,
    cellCycle,
  });
}

/** Build the ring-translation cell cycle by matching each cell's forward-shifted
 * vertex set back to a generated cell. `shift` is the per-axis forward step in
 * the first lattice coordinate (1 for the unit grids, 2 for the hex column
 * lattice). Returns null when the shift is not a bijection over the cells. */
function ringCycleByVertexSet(
  cells: Cells,
  cellVerts: Map<CellId, [number, number][]>,
  key: (a: number, b: number) => [number, number],
  shift = 1,
): Map<CellId, CellId> | null {
  const byVertexSet = new Map<string, CellId>();
  for (const [cell, keys] of cells) byVertexSet.set(vertexSetKey(keys), cell);
  const cellCycle = new Map<CellId, CellId>();
  for (const [cell, verts] of cellVerts) {
    const shifted = verts.map(([a, b]) => {
      const [ca, cb] = key(a + shift, b);
      return `${ca},${cb}`;
    });
    const target = byVertexSet.get(vertexSetKey(shifted));
    if (target === undefined) return null;
    cellCycle.set(cell, target);
  }
  if (new Set(cellCycle.values()).size !== cellCycle.size) return null;
  return cellCycle;
}

// -- the cylinder ------------------------------------------------------------

/** The side surface of a cylinder tiled with quadrilaterals: `ring` segments
 * around, `rows` up the axis. Open ends, so the inside is visible. */
export function cylinderBoard(ring: number, rows: number, mineCount: number): Board3D {
  const rowHeight = (TWO_PI / ring) * 0.9; // near-square tiles
  const height = rows * rowHeight;
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (i: number, j: number): string => {
    const k = `${i},${j}`;
    if (!positions.has(k)) {
      positions.set(k, cylinderPoint(TWO_PI * i / ring, j * rowHeight - height / 2));
    }
    return k;
  };
  for (let i = 0; i < ring; i++) {
    for (let j = 0; j < rows; j++) {
      cells.set(cid(i, j), [put(i, j), put((i + 1) % ring, j), put((i + 1) % ring, j + 1), put(i, j + 1)]);
    }
  }
  return assemble("cylinder", cells, positions, mineCount, {
    twoSided: true,
    radius: Math.hypot(1, height / 2),
  });
}

/** The side of a cylinder tiled with triangles: `ring` triangles around (must
 * be even so up/down triangles alternate across the seam), `rows` up. */
export function cylinderTriangleBoard(ring: number, rows: number, mineCount: number): Board3D {
  if (ring % 2) throw new Error("ring must be even for the triangle strip to wrap");
  const rowHeight = (TWO_PI / ring) * ROOT3 * 0.9;
  const height = rows * rowHeight;
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (kx: number, ky: number): string => {
    const wx = ((kx % ring) + ring) % ring;
    const k = `${wx},${ky}`;
    if (!positions.has(k)) {
      positions.set(k, cylinderPoint(TWO_PI * wx / ring, ky * rowHeight - height / 2));
    }
    return k;
  };
  for (let r = 0; r < rows; r++) {
    for (let i = 0; i < ring; i++) {
      cells.set(
        cid(r, i),
        triangleVertices(i, r, (r + i) % 2 === 0).map(([kx, ky]) => put(kx, ky)),
      );
    }
  }
  return assemble("cyltri", cells, positions, mineCount, {
    twoSided: true,
    radius: Math.hypot(1, height / 2),
  });
}

/** The side of a cylinder tiled with hexagons: `ring` columns around, `rows`
 * up the axis. */
export function cylinderHexBoard(ring: number, rows: number, mineCount: number): Board3D {
  const kxPeriod = 2 * ring;
  const kyUnit = TWO_PI / kxPeriod / ROOT3;
  const height = (3 * rows + 1) * kyUnit;
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const put = (kx: number, ky: number): string => {
    const wx = ((kx % kxPeriod) + kxPeriod) % kxPeriod;
    const k = `${wx},${ky}`;
    if (!positions.has(k)) {
      positions.set(k, cylinderPoint(TWO_PI * wx / kxPeriod, ky * kyUnit - height / 2));
    }
    return k;
  };
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < ring; c++) {
      const kx = 2 * c + (r % 2) + 1;
      const ky = 3 * r + 2;
      cells.set(
        cid(r, c),
        HEX_VERTEX_OFFSETS.map(([ox, oy]) => put(kx + ox, ky + oy)),
      );
    }
  }
  return assemble("cylhex", cells, positions, mineCount, {
    twoSided: true,
    radius: Math.hypot(1, height / 2),
  });
}
