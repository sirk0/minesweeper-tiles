// Port of minesweeper/boards/aperiodic.py — the two aperiodic flat tilings,
// Penrose (P3 rhombi) and the Hat monotile. Both build float vertex positions
// but keep *exact* integer vertex ids, so shared-vertex adjacency needs no
// tolerance (Penrose over ℤ[ζ5], the Hat over the Eisenstein lattice). Cell ids
// and structure mirror the Python source so the two stay diffable.

import { type Board, type CellId, cid, finalizeFlat, type Vertex } from "./core";

const ROOT3 = Math.sqrt(3);

// -- Penrose tiling (P3, rhombi) ---------------------------------------------
//
// Vertices are exact elements of ℤ[ζ], ζ = exp(iπ/5), stored as 4 integer
// coefficients over the basis (1, z, z², z³) with the reduction
// z⁴ = -1 + z - z² + z³. Robinson-triangle deflation only ever needs addition,
// subtraction and division by φ — and 1/φ = φ - 1 = z² - z³ — so every
// operation stays in integers and vertex keys are exact.

type ZPoint = readonly [number, number, number, number];

function zetaMul(p: ZPoint): ZPoint {
  const [a, b, c, d] = p;
  return [-d, a + d, b - d, c + d];
}

function zAdd(p: ZPoint, q: ZPoint): ZPoint {
  return [p[0] + q[0], p[1] + q[1], p[2] + q[2], p[3] + q[3]];
}

function zSub(p: ZPoint, q: ZPoint): ZPoint {
  return [p[0] - q[0], p[1] - q[1], p[2] - q[2], p[3] - q[3]];
}

function zDivPhi(p: ZPoint): ZPoint {
  const z2 = zetaMul(zetaMul(p));
  return zSub(z2, zetaMul(z2));
}

const ZETA_BASIS: Vertex[] = [0, 1, 2, 3].map((k) => [
  Math.cos((Math.PI * k) / 5),
  Math.sin((Math.PI * k) / 5),
]);

function zToXy(p: ZPoint): Vertex {
  let x = 0;
  let y = 0;
  for (let i = 0; i < 4; i++) {
    x += p[i]! * ZETA_BASIS[i]![0];
    y += p[i]! * ZETA_BASIS[i]![1];
  }
  return [x, y];
}

const zKey = (p: ZPoint): string => p.join(",");

/** Lexicographic order on ℤ[ζ5] coefficient tuples (matches Python tuple sort,
 * used only to canonicalise a rhombus's shared base edge). */
function zCmp(a: ZPoint, b: ZPoint): number {
  for (let i = 0; i < 4; i++) {
    if (a[i]! !== b[i]!) return a[i]! - b[i]!;
  }
  return 0;
}

interface PenroseCell {
  color: number;
  index: number;
  verts: ZPoint[];
}

/**
 * An aperiodic Penrose tiling (P3): thick and thin rhombi. Starts from a wheel
 * of ten half-rhombus Robinson triangles, deflates `subdivisions` times, then
 * merges mirror-image triangle halves into rhombi (unpaired rim halves are
 * dropped). `scale` is the wheel radius in pixels; `keep` trims to the `keep`
 * centremost rhombi by Chebyshev distance (a roughly square block); `null`
 * keeps the whole decagonal patch.
 */
export function penroseBoard(
  subdivisions: number,
  mineCount: number,
  scale = 300,
  keep: number | null = null,
): Board {
  const zero: ZPoint = [0, 0, 0, 0];
  const powers: ZPoint[] = [[1, 0, 0, 0]];
  for (let i = 0; i < 10; i++) powers.push(zetaMul(powers[powers.length - 1]!));

  // (color, apex, base1, base2): color 0 = half-thin, 1 = half-thick.
  let triangles: [number, ZPoint, ZPoint, ZPoint][] = [];
  for (let i = 0; i < 10; i++) {
    let b = powers[i]!;
    let c = powers[i + 1]!;
    if (i % 2) [b, c] = [c, b]; // alternate handedness so mirror halves pair up
    triangles.push([0, zero, b, c]);
  }

  for (let s = 0; s < subdivisions; s++) {
    const deflated: [number, ZPoint, ZPoint, ZPoint][] = [];
    for (const [color, a, b, c] of triangles) {
      if (color === 0) {
        const p = zAdd(a, zDivPhi(zSub(b, a)));
        deflated.push([0, c, p, b], [1, p, c, a]);
      } else {
        const q = zAdd(b, zDivPhi(zSub(a, b)));
        const r = zAdd(b, zDivPhi(zSub(c, b)));
        deflated.push([1, r, c, a], [1, q, r, b], [0, r, q, a]);
      }
    }
    triangles = deflated;
  }

  if (import.meta.env.DEV) {
    for (const [, a, b, c] of triangles) {
      for (const p of [a, b, c]) {
        for (const coeff of p) {
          if (!Number.isSafeInteger(coeff)) {
            throw new Error(`Penrose ℤ[ζ5] coefficient overflow: ${coeff}`);
          }
        }
      }
    }
  }

  // Merge mirror halves: partners share the colour and the base edge.
  const waiting = new Map<string, ZPoint>();
  const cells: PenroseCell[] = [];
  for (const [color, a, b, c] of triangles) {
    const edge = zCmp(b, c) <= 0 ? `${zKey(b)}|${zKey(c)}` : `${zKey(c)}|${zKey(b)}`;
    const key = `${color}|${edge}`;
    const otherApex = waiting.get(key);
    if (otherApex !== undefined) {
      waiting.delete(key);
      cells.push({ color, index: cells.length, verts: [a, b, otherApex, c] });
    } else {
      waiting.set(key, a);
    }
  }

  let kept = cells;
  if (keep !== null && keep < cells.length) {
    const centroid = new Map<PenroseCell, Vertex>();
    for (const cell of cells) {
      let cx = 0;
      let cy = 0;
      for (const v of cell.verts) {
        const [x, y] = zToXy(v);
        cx += x;
        cy += y;
      }
      centroid.set(cell, [cx / 4, cy / 4]);
    }
    let gx = 0;
    let gy = 0;
    for (const c of centroid.values()) {
      gx += c[0];
      gy += c[1];
    }
    gx /= cells.length;
    gy /= cells.length;
    const cheb = (cell: PenroseCell): number => {
      const c = centroid.get(cell)!;
      return Math.max(Math.abs(c[0] - gx), Math.abs(c[1] - gy));
    };
    kept = [...cells].sort(
      (m, n) => cheb(m) - cheb(n) || m.color - n.color || m.index - n.index,
    );
    kept = kept.slice(0, keep);
  }

  const cellMap = new Map<CellId, string[]>();
  const positions = new Map<string, Vertex>();
  for (const cell of kept) {
    const keys = cell.verts.map((v) => {
      const k = zKey(v);
      if (!positions.has(k)) positions.set(k, zToXy(v));
      return k;
    });
    cellMap.set(cid(cell.color, cell.index), keys);
  }
  return finalizeFlat("penrose", cellMap, positions, mineCount, scale);
}

// -- The Hat: an aperiodic monotile ------------------------------------------
//
// "The Hat" (Smith–Myers–Kaplan–Goodman-Strauss, 2023) is a single 13-sided
// tile that tiles the plane only aperiodically. Every hat vertex lies on the
// Eisenstein integer lattice — point (a, b) is a·(1,0) + b·(1/2, √3/2) =
// hexPt(a, b) — so a vertex id is an exact integer pair. The tiling grows by
// the H/T/P/F metatile substitution (transforms ported from Craig S. Kaplan's
// "hatviz", BSD 3-Clause, © 2023 Craig S. Kaplan). Those transforms carry
// irrational (√3) translations so they run in floating point; each final vertex
// snaps back to its exact Eisenstein id, so float is transient and seams are
// impossible.

const HR3 = ROOT3 / 2;
type Pt = readonly [number, number];
// 2×3 affine (a, b, c, d, e, f): x' = ax + by + c, y' = dx + ey + f.
type Aff = readonly [number, number, number, number, number, number];
const AFF_IDENT: Aff = [1, 0, 0, 0, 1, 0];

function affMul(A: Aff, B: Aff): Aff {
  return [
    A[0] * B[0] + A[1] * B[3],
    A[0] * B[1] + A[1] * B[4],
    A[0] * B[2] + A[1] * B[5] + A[2],
    A[3] * B[0] + A[4] * B[3],
    A[3] * B[1] + A[4] * B[4],
    A[3] * B[2] + A[4] * B[5] + A[5],
  ];
}

function affInv(T: Aff): Aff {
  const det = T[0] * T[4] - T[1] * T[3];
  return [
    T[4] / det,
    -T[1] / det,
    (T[1] * T[5] - T[2] * T[4]) / det,
    -T[3] / det,
    T[0] / det,
    (T[2] * T[3] - T[0] * T[5]) / det,
  ];
}

function affPt(M: Aff, p: Pt): Pt {
  return [M[0] * p[0] + M[1] * p[1] + M[2], M[3] * p[0] + M[4] * p[1] + M[5]];
}

function trot(ang: number): Aff {
  const c = Math.cos(ang);
  const s = Math.sin(ang);
  return [c, -s, 0, s, c, 0];
}

function ttrans(tx: number, ty: number): Aff {
  return [1, 0, tx, 0, 1, ty];
}

function rotAbout(p: Pt, ang: number): Aff {
  return affMul(ttrans(p[0], p[1]), affMul(trot(ang), ttrans(-p[0], -p[1])));
}

function matchSeg(p: Pt, q: Pt): Aff {
  return [q[0] - p[0], p[1] - q[1], p[0], q[1] - p[1], q[0] - p[0], p[1]];
}

function matchTwo(p1: Pt, q1: Pt, p2: Pt, q2: Pt): Aff {
  return affMul(matchSeg(p2, q2), affInv(matchSeg(p1, q1)));
}

function lineIntersect(p1: Pt, q1: Pt, p2: Pt, q2: Pt): Pt {
  const d = (q2[1] - p2[1]) * (q1[0] - p1[0]) - (q2[0] - p2[0]) * (q1[1] - p1[1]);
  const u =
    ((q2[0] - p2[0]) * (p1[1] - p2[1]) - (q2[1] - p2[1]) * (p1[0] - p2[0])) / d;
  return [p1[0] + u * (q1[0] - p1[0]), p1[1] + u * (q1[1] - p1[1])];
}

function hexPt(a: number, b: number): Vertex {
  return [a + 0.5 * b, HR3 * b];
}

// The hat as its 13 corners (Kaplan's hat_outline) — a true tridecagon. All 13
// are exact lattice points, capturing every shared vertex.
const HAT_OUTLINE: Pt[] = [
  hexPt(0, 0), hexPt(-1, -1), hexPt(0, -2), hexPt(2, -2), hexPt(2, -1),
  hexPt(4, -2), hexPt(5, -1), hexPt(4, 0), hexPt(3, 0), hexPt(2, 2),
  hexPt(0, 3), hexPt(0, 2), hexPt(-1, 2),
];

class HatTile {
  constructor(readonly label: string) {}
}

class MetaTile {
  shape: Pt[];
  children: [Aff, Geom][] = [];
  constructor(
    shape: Pt[],
    readonly width: number,
  ) {
    this.shape = shape;
  }

  addChild(T: Aff, geom: Geom): void {
    this.children.push([T, geom]);
  }

  evalChild(n: number, i: number): Pt {
    const [T, geom] = this.children[n]!;
    return affPt(T, (geom as MetaTile).shape[i]!);
  }

  recentre(): void {
    let cx = 0;
    let cy = 0;
    for (const p of this.shape) {
      cx += p[0];
      cy += p[1];
    }
    cx /= this.shape.length;
    cy /= this.shape.length;
    this.shape = this.shape.map(([x, y]) => [x - cx, y - cy]);
    const M = ttrans(-cx, -cy);
    this.children = this.children.map(([T, geom]) => [affMul(M, T), geom]);
  }
}

type Geom = HatTile | MetaTile;

// The four metatile substitution rules (verbatim from hatviz). Each rule places
// one child relative to already-placed children; see constructPatch.
const HAT_RULES: (number | string)[][] = [
  ["H"],
  [0, 0, "P", 2], [1, 0, "H", 2], [2, 0, "P", 2], [3, 0, "H", 2],
  [4, 4, "P", 2], [0, 4, "F", 3], [2, 4, "F", 3],
  [4, 1, 3, 2, "F", 0],
  [8, 3, "H", 0], [9, 2, "P", 0], [10, 2, "H", 0], [11, 4, "P", 2],
  [12, 0, "H", 2], [13, 0, "F", 3], [14, 2, "F", 1], [15, 3, "H", 4],
  [8, 2, "F", 1], [17, 3, "H", 0], [18, 2, "P", 0], [19, 2, "H", 2],
  [20, 4, "F", 3], [20, 0, "P", 2], [22, 0, "H", 2], [23, 4, "F", 3],
  [23, 0, "F", 3], [16, 0, "P", 2],
  [9, 4, 0, 2, "T", 2],
  [4, 0, "F", 3],
];

/** The four level-0 metatiles H, T, P, F, each a cluster of hats. */
function hatBaseTiles(): MetaTile[] {
  const H1 = new HatTile("H1");
  const H = new HatTile("H");
  const T = new HatTile("T");
  const P = new HatTile("P");
  const F = new HatTile("F");
  const o = HAT_OUTLINE;

  const Hout: Pt[] = [
    [0, 0], [4, 0], [4.5, HR3], [2.5, 5 * HR3], [1.5, 5 * HR3], [-0.5, HR3],
  ];
  const hm = new MetaTile(Hout, 2);
  hm.addChild(matchTwo(o[5]!, o[7]!, Hout[5]!, Hout[0]!), H);
  hm.addChild(matchTwo(o[9]!, o[11]!, Hout[1]!, Hout[2]!), H);
  hm.addChild(matchTwo(o[5]!, o[7]!, Hout[3]!, Hout[4]!), H);
  hm.addChild(
    affMul(
      ttrans(2.5, HR3),
      affMul([-0.5, -HR3, 0, HR3, -0.5, 0], [0.5, 0, 0, 0, -0.5, 0]),
    ),
    H1,
  );

  const tm = new MetaTile([[0, 0], [3, 0], [1.5, 3 * HR3]], 2);
  tm.addChild([0.5, 0, 0.5, 0, 0.5, HR3], T);

  const pm = new MetaTile([[0, 0], [4, 0], [3, 2 * HR3], [-1, 2 * HR3]], 2);
  pm.addChild([0.5, 0, 1.5, 0, 0.5, HR3], P);
  pm.addChild(
    affMul(
      ttrans(0, 2 * HR3),
      affMul([0.5, HR3, 0, -HR3, 0.5, 0], [0.5, 0, 0, 0, 0.5, 0]),
    ),
    P,
  );

  const fm = new MetaTile(
    [[0, 0], [3, 0], [3.5, HR3], [3, 2 * HR3], [-1, 2 * HR3]],
    2,
  );
  fm.addChild([0.5, 0, 1.5, 0, 0.5, HR3], F);
  fm.addChild(
    affMul(
      ttrans(0, 2 * HR3),
      affMul([0.5, HR3, 0, -HR3, 0.5, 0], [0.5, 0, 0, 0, 0.5, 0]),
    ),
    F,
  );

  return [hm, tm, pm, fm];
}

function constructPatch(H: MetaTile, T: MetaTile, P: MetaTile, F: MetaTile): MetaTile {
  const shapes: Record<string, MetaTile> = { H, T, P, F };
  const ret = new MetaTile([], H.width);
  for (const r of HAT_RULES) {
    if (r.length === 1) {
      ret.addChild(AFF_IDENT, shapes[r[0] as string]!);
    } else if (r.length === 4) {
      const [Tc, geom] = ret.children[r[0] as number]!;
      const poly = (geom as MetaTile).shape;
      const n = poly.length;
      const p = affPt(Tc, poly[((r[1] as number) + 1) % n]!);
      const q = affPt(Tc, poly[r[1] as number]!);
      const npoly = shapes[r[2] as string]!.shape;
      const m = npoly.length;
      ret.addChild(
        matchTwo(npoly[r[3] as number]!, npoly[((r[3] as number) + 1) % m]!, p, q),
        shapes[r[2] as string]!,
      );
    } else {
      const [TP, gP] = ret.children[r[0] as number]!;
      const [TQ, gQ] = ret.children[r[2] as number]!;
      const p = affPt(TQ, (gQ as MetaTile).shape[r[3] as number]!);
      const q = affPt(TP, (gP as MetaTile).shape[r[1] as number]!);
      const npoly = shapes[r[4] as string]!.shape;
      const m = npoly.length;
      ret.addChild(
        matchTwo(npoly[r[5] as number]!, npoly[((r[5] as number) + 1) % m]!, p, q),
        shapes[r[4] as string]!,
      );
    }
  }
  return ret;
}

/** Assemble the next-level H, T, P, F supertiles from a patch. */
function constructMetatiles(patch: MetaTile): MetaTile[] {
  const bps1 = patch.evalChild(8, 2);
  const bps2 = patch.evalChild(21, 2);
  const rbps = affPt(rotAbout(bps1, (-2 * Math.PI) / 3), bps2);
  const p72 = patch.evalChild(7, 2);
  const p252 = patch.evalChild(25, 2);

  const e62 = patch.evalChild(6, 2);
  const llc = lineIntersect(bps1, rbps, e62, p72);
  let w: Pt = [e62[0] - llc[0], e62[1] - llc[1]];

  const nH: Pt[] = [llc, bps1];
  w = affPt(trot(-Math.PI / 3), w);
  nH.push([nH[1]![0] + w[0], nH[1]![1] + w[1]]);
  nH.push(patch.evalChild(14, 2));
  w = affPt(trot(-Math.PI / 3), w);
  nH.push([nH[3]![0] - w[0], nH[3]![1] - w[1]]);
  nH.push(e62);
  const newH = new MetaTile(nH, patch.width * 2);
  for (const ch of [0, 9, 16, 27, 26, 6, 1, 8, 10, 15]) {
    newH.addChild(...patch.children[ch]!);
  }

  const nP: Pt[] = [
    p72,
    [p72[0] + bps1[0] - llc[0], p72[1] + bps1[1] - llc[1]],
    bps1,
    llc,
  ];
  const newP = new MetaTile(nP, patch.width * 2);
  for (const ch of [7, 2, 3, 4, 28]) newP.addChild(...patch.children[ch]!);

  const nF: Pt[] = [
    bps2,
    patch.evalChild(24, 2),
    patch.evalChild(25, 0),
    p252,
    [p252[0] + llc[0] - bps1[0], p252[1] + llc[1] - bps1[1]],
  ];
  const newF = new MetaTile(nF, patch.width * 2);
  for (const ch of [21, 20, 22, 23, 24, 25]) newF.addChild(...patch.children[ch]!);

  const AAA = nH[2]!;
  const BBB: Pt = [
    nH[1]![0] + nH[4]![0] - nH[5]![0],
    nH[1]![1] + nH[4]![1] - nH[5]![1],
  ];
  const CCC = affPt(rotAbout(BBB, -Math.PI / 3), AAA);
  const newT = new MetaTile([BBB, CCC, AAA], patch.width * 2);
  newT.addChild(...patch.children[11]!);

  for (const m of [newH, newP, newF, newT]) m.recentre();
  return [newH, newT, newP, newF];
}

function hatLeaves(geom: Geom, M: Aff, out: [string, Aff][]): void {
  if (geom instanceof HatTile) {
    out.push([geom.label, M]);
  } else {
    for (const [T, child] of geom.children) hatLeaves(child, affMul(M, T), out);
  }
}

function hatSnap(p: Pt): [number, number] {
  const b = Math.round((2 * p[1]) / HR3);
  const a = Math.round(2 * p[0] - 0.5 * b);
  return [a, b];
}

interface HatRow {
  label: string;
  ids: [number, number][];
  sortedIds: [number, number][];
  cx: number;
  cy: number;
}

const cmpId = (x: [number, number], y: [number, number]): number =>
  x[0] - y[0] || x[1] - y[1];

/** Lexicographic order on two hats' sorted vertex-id lists (equal length). */
function cmpSortedIds(A: [number, number][], B: [number, number][]): number {
  const n = Math.min(A.length, B.length);
  for (let i = 0; i < n; i++) {
    const c = cmpId(A[i]!, B[i]!);
    if (c) return c;
  }
  return A.length - B.length;
}

/**
 * The Hat aperiodic monotile, grown by `levels` of the H/T/P/F metatile
 * substitution from a single H seed. `keep` trims the patch to its `keep`
 * centremost hats by Chebyshev distance (a roughly square board with an exact
 * cell count); `null` keeps the whole (ragged, star-shaped) patch.
 */
export function hatBoard(
  levels: number,
  mineCount: number,
  keep: number | null = null,
  scale = 14,
): Board {
  let tiles = hatBaseTiles();
  for (let i = 0; i < levels; i++) {
    tiles = constructMetatiles(constructPatch(tiles[0]!, tiles[1]!, tiles[2]!, tiles[3]!));
  }
  const hats: [string, Aff][] = [];
  hatLeaves(tiles[0]!, AFF_IDENT, hats);

  const rows: HatRow[] = [];
  const seen = new Set<string>();
  for (const [label, M] of hats) {
    const ids = HAT_OUTLINE.map((p) => hatSnap(affPt(M, p)));
    const sortedIds = [...ids].sort(cmpId);
    const fs = sortedIds.map((v) => `${v[0]},${v[1]}`).join(";");
    if (seen.has(fs)) continue; // defensive: a single H seed produces no dups
    seen.add(fs);
    let cx = 0;
    let cy = 0;
    for (const v of ids) {
      const [x, y] = hexPt(v[0], v[1]);
      cx += x;
      cy += y;
    }
    rows.push({ label, ids, sortedIds, cx: cx / ids.length, cy: cy / ids.length });
  }

  let kept = rows;
  if (keep !== null && keep < rows.length) {
    let gx = 0;
    let gy = 0;
    for (const r of rows) {
      gx += r.cx;
      gy += r.cy;
    }
    gx /= rows.length;
    gy /= rows.length;
    const cheb = (r: HatRow): number =>
      Math.max(Math.abs(r.cx - gx), Math.abs(r.cy - gy));
    kept = [...rows].sort(
      (r1, r2) => cheb(r1) - cheb(r2) || cmpSortedIds(r1.sortedIds, r2.sortedIds),
    );
    kept = kept.slice(0, keep);
  }

  const cellMap = new Map<CellId, string[]>();
  const positions = new Map<string, Vertex>();
  kept.forEach((row, i) => {
    const keys = row.ids.map((v) => {
      const k = `${v[0]},${v[1]}`;
      if (!positions.has(k)) positions.set(k, hexPt(v[0], v[1]));
      return k;
    });
    cellMap.set(cid(row.label, i), keys);
  });
  return finalizeFlat("hat", cellMap, positions, mineCount, scale);
}
