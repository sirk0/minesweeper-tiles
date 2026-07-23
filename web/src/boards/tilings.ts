// Port of the regular flat lattice builders in minesweeper/boards/tilings.py
// (square / triangle / trigrid / hex / hexhex). Integer lattice points, so
// adjacency uses exact vertex keys — no quantization needed here.
import {
  buildLattice,
  cid,
  finalizeFlat,
  type Board,
  type CellId,
  type Vertex,
} from "./core";

const ROOT3 = Math.sqrt(3);
const DEG = Math.PI / 180;

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

// -- Archimedean (semiregular) tilings + Laves duals -------------------------
//
// Port of the `_ArchTemplate` system in minesweeper/boards/tilings.py. Each of
// the eight non-regular uniform tilings and its Laves (dual) partner is built
// from one rectangular fundamental domain: vertices are canonicalized into the
// domain, cells are references into this or a neighbouring domain copy. The
// same template drives the flat window (`archimedeanBoard`) and the surface
// wraps in surfaces.ts. Tags are the exact-position hashable ids: a string
// `"rx,ry"` of the domain-local coordinates rounded to 1e-6 (Python rounds tag
// tuples the same), so two cells are neighbours iff they share a tag.

/** A tag reference: which vertex (`tag`) in which domain copy (`dm`, `dn`). */
export interface Ref {
  tag: string;
  dm: number;
  dn: number;
}

export interface ArchTemplate {
  config: number[]; // vertex configuration, e.g. [3, 6, 3, 6]
  width: number; // domain size in edge lengths
  height: number;
  verts: Map<string, Vertex>; // tag -> position within the domain
  cells: { name: string; refs: Ref[] }[];
  mirror: Map<string, Ref> | null; // tag -> image under y -> height - y
  glide: boolean; // the mirror needs an extra width/2 x-shift (p4g)
  centre: Vertex | null; // rotation centre (domain coords) for the flat window
}

type Polygon = readonly (readonly [number, number])[];

/** Round to 6 decimals and normalise -0 to 0 (matches Python `round(v, 6)`). */
function round6(v: number): number {
  const r = Math.round(v * 1e6) / 1e6;
  return r + 0;
}

/** Build a template from one domain's worth of cell polygons in float
 * coordinates. Each vertex is canonicalized into [0, width) x [0, height); the
 * rounded canonical position doubles as its exact hashable tag. */
function template(
  config: number[],
  width: number,
  height: number,
  polygons: readonly (readonly [string, Polygon])[],
  { mirrored = true, glide = false, centre = null as Vertex | null } = {},
): ArchTemplate {
  const reduce = (value: number, size: number): [number, number] => {
    // the slack absorbs tag rounding, so values exactly on a domain edge land
    // on its near side; real vertices are never this close without being on it
    const d = Math.floor(value / size + 1e-5);
    return [round6(value - d * size), d];
  };
  const canonical = (x: number, y: number): { tag: string; xy: Vertex; dm: number; dn: number } => {
    const [rx, dm] = reduce(x, width);
    const [ry, dn] = reduce(y, height);
    return { tag: `${rx},${ry}`, xy: [rx, ry], dm, dn };
  };

  const verts = new Map<string, Vertex>();
  const cells: { name: string; refs: Ref[] }[] = [];
  for (const [name, polygon] of polygons) {
    let refs: Ref[] = [];
    for (const [x, y] of polygon) {
      const c = canonical(x, y);
      verts.set(c.tag, c.xy);
      refs.push({ tag: c.tag, dm: c.dm, dn: c.dn });
    }
    // normalize so the cell's centroid lies in domain copy (0, 0): the Möbius
    // builder selects cell instances by centroid
    let cx = 0;
    let cy = 0;
    for (const r of refs) {
      const v = verts.get(r.tag)!;
      cx += r.dm * width + v[0];
      cy += r.dn * height + v[1];
    }
    cx /= refs.length;
    cy /= refs.length;
    const mshift = Math.floor(cx / width + 1e-9);
    const nshift = Math.floor(cy / height + 1e-9);
    refs = refs.map((r) => ({ tag: r.tag, dm: r.dm - mshift, dn: r.dn - nshift }));
    cells.push({ name, refs });
  }

  const wrapGap = (delta: number, size: number): number => {
    const d = Math.abs(delta) % size;
    return Math.min(d, size - d);
  };
  const distance = (xy: Vertex, x: number, y: number): number =>
    Math.hypot(wrapGap(xy[0] - x, width), wrapGap(xy[1] - y, height));

  let mirror: Map<string, Ref> | null = null;
  if (mirrored) {
    const shift = glide ? width / 2 : 0;
    mirror = new Map();
    for (const [tag, xy] of verts) {
      const x = xy[0] + shift;
      const y = height - xy[1];
      const c = canonical(x, y);
      let image = c.tag;
      if (!verts.has(image)) {
        // tags are rounded; match the closest vertex (wrap-aware)
        let best = Infinity;
        for (const [vt, vxy] of verts) {
          const dd = distance(vxy, x, y);
          if (dd < best) {
            best = dd;
            image = vt;
          }
        }
        if (distance(verts.get(image)!, x, y) > 1e-4) {
          throw new Error(`mirror of ${tag} is not a vertex`);
        }
      }
      mirror.set(tag, { tag: image, dm: c.dm, dn: c.dn });
    }
  }
  return { config, width, height, verts, cells, mirror, glide, centre };
}

function regularPolygon(
  cx: number,
  cy: number,
  sides: number,
  circumradius: number,
  offsetDeg: number,
): Vertex[] {
  const out: Vertex[] = [];
  for (let k = 0; k < sides; k++) {
    const a = (offsetDeg + (360 * k) / sides) * DEG;
    out.push([cx + circumradius * Math.cos(a), cy + circumradius * Math.sin(a)]);
  }
  return out;
}

/** The unit square sitting outside the edge whose outward normal is
 * `normalDeg` at distance `apothem` from (cx, cy). */
function squareOnEdge(cx: number, cy: number, apothem: number, normalDeg: number): Vertex[] {
  const phi = normalDeg * DEG;
  const ux = Math.cos(phi);
  const uy = Math.sin(phi);
  const tx = -uy;
  const ty = ux; // along the edge
  const mx = cx + apothem * ux;
  const my = cy + apothem * uy;
  const a: Vertex = [mx + 0.5 * tx, my + 0.5 * ty];
  const b: Vertex = [mx - 0.5 * tx, my - 0.5 * ty];
  return [a, b, [b[0] + ux, b[1] + uy], [a[0] + ux, a[1] + uy]];
}

/** Assemble one rectangular domain of a tiling built on a triangular lattice of
 * hexagon (or dodecagon) centres. `hexagonAt` is the central polygon around a
 * lattice point and `decorate` yields the polygons hung off it; everything is
 * deduplicated by rounded centroid and kept when its centroid lands in
 * [0, width) x [0, height). */
function hexLatticePolygons(
  centreAt: (m: number, n: number) => Vertex,
  hexagonAt: (cx: number, cy: number) => Vertex[],
  decorate: (cx: number, cy: number) => [string, Vertex[]][],
  width: number,
  height: number,
): [string, Vertex[]][] {
  const centroid = (polygon: Polygon): Vertex => {
    let x = 0;
    let y = 0;
    for (const p of polygon) {
      x += p[0];
      y += p[1];
    }
    return [x / polygon.length, y / polygon.length];
  };
  const polygons = new Map<string, Vertex[]>();
  for (let m = -2; m < 4; m++) {
    for (let n = -2; n < 4; n++) {
      const [cx, cy] = centreAt(m, n);
      const entries: [string, Vertex[]][] = [["c", hexagonAt(cx, cy)], ...decorate(cx, cy)];
      for (const [name, polygon] of entries) {
        const [gx, gy] = centroid(polygon);
        if (-1e-9 <= gx && gx < width - 1e-9 && -1e-9 <= gy && gy < height - 1e-9) {
          polygons.set(`${name},${round3(gx)},${round3(gy)}`, polygon);
        }
      }
    }
  }
  let i = 0;
  const out: [string, Vertex[]][] = [];
  for (const [key, polygon] of polygons) {
    const name = key.slice(0, key.indexOf(","));
    out.push([`${name}${i}`, polygon]);
    i++;
  }
  return out;
}

function round3(v: number): number {
  return Math.round(v * 1e3) / 1e3 + 0;
}

// -- the eight uniform template factories ------------------------------------

function kagomeTemplate(): ArchTemplate {
  // Kagome (3.6.3.6): hexagon centres on a side-2 triangular lattice, cell
  // vertices at the lattice edge midpoints.
  const h = ROOT3 / 2;
  const hexagon = (cx: number, cy: number): Vertex[] => [
    [cx + 1, cy],
    [cx + 0.5, cy + h],
    [cx - 0.5, cy + h],
    [cx - 1, cy],
    [cx - 0.5, cy - h],
    [cx + 0.5, cy - h],
  ];
  const polygons: [string, Vertex[]][] = [
    ["hex0", hexagon(0, 0)],
    ["hex1", hexagon(1, ROOT3)],
    ["tri0", [[1, 0], [1.5, h], [0.5, h]]],
    ["tri1", [[1.5, h], [2, ROOT3], [2.5, h]]],
    ["tri2", [[2, ROOT3], [2.5, ROOT3 + h], [1.5, ROOT3 + h]]],
    ["tri3", [[1.5, ROOT3 + h], [1, 2 * ROOT3], [0.5, ROOT3 + h]]],
  ];
  return template([3, 6, 3, 6], 2, 2 * ROOT3, polygons);
}

function truncsquareTemplate(): ArchTemplate {
  // Truncated square (4.8.8): octagons on a square lattice of pitch 1 + sqrt(2),
  // tilted unit squares filling the corners.
  const a = 1 + Math.SQRT2;
  const p = a / 2;
  const q = Math.SQRT2 / 2;
  const octagon: Vertex[] = [
    [0.5, p],
    [p, 0.5],
    [p, -0.5],
    [0.5, -p],
    [-0.5, -p],
    [-p, -0.5],
    [-p, 0.5],
    [-0.5, p],
  ];
  const square: Vertex[] = [
    [p - q, p],
    [p, p - q],
    [p + q, p],
    [p, p + q],
  ];
  return template([4, 8, 8], a, a, [["oct", octagon], ["sq", square]]);
}

function elongatedTemplate(): ArchTemplate {
  // Elongated triangular (3.3.3.4.4): rows of squares separated by rows of
  // triangles, consecutive square rows offset by half a square.
  const h = ROOT3 / 2;
  const polygons: [string, Vertex[]][] = [
    ["sq0", [[0, -0.5], [1, -0.5], [1, 0.5], [0, 0.5]]],
    ["tri0", [[0, 0.5], [1, 0.5], [0.5, 0.5 + h]]],
    ["tri1", [[0.5, 0.5 + h], [1, 0.5], [1.5, 0.5 + h]]],
    ["sq1", [[0.5, 0.5 + h], [1.5, 0.5 + h], [1.5, 1.5 + h], [0.5, 1.5 + h]]],
    ["tri2", [[0.5, 1.5 + h], [1.5, 1.5 + h], [1, 1.5 + 2 * h]]],
    ["tri3", [[1, 1.5 + 2 * h], [1.5, 1.5 + h], [2, 1.5 + 2 * h]]],
  ];
  return template([3, 3, 3, 4, 4], 1, 2 + ROOT3, polygons);
}

function snubsquareTemplate(): ArchTemplate {
  // Snub square (3.3.4.3.4): squares alternately rotated +-15 degrees, pairs of
  // triangles between them. p4g has only a glide (mirror plus half a period).
  const a = Math.sqrt(2 + ROOT3);
  const r = Math.SQRT1_2;
  const square = (cx: number, cy: number, firstCorner: number): Vertex[] => {
    const out: Vertex[] = [];
    for (let k = 0; k < 4; k++) {
      const ang = (firstCorner + 90 * k) * DEG;
      out.push([cx + r * Math.cos(ang), cy + r * Math.sin(ang)]);
    }
    return out;
  };
  const triOn = (points: Vertex[], center: Vertex, k: number): Vertex[] => {
    // the equilateral triangle on edge k of a square, apex away from it
    const [x1, y1] = points[k]!;
    const [x2, y2] = points[(k + 1) % 4]!;
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const apex: Vertex = [mx + ROOT3 * (mx - center[0]), my + ROOT3 * (my - center[1])];
    return [[x1, y1], [x2, y2], apex];
  };
  const plus = square(0, a / 4, 60); // rotated +15
  const minus = square(a / 2, (3 * a) / 4, 30); // rotated -15
  const polygons: [string, Vertex[]][] = [
    ["sq0", plus],
    ["sq1", minus],
    ["tri0", triOn(plus, [0, a / 4], 0)],
    ["tri1", triOn(plus, [0, a / 4], 2)],
    ["tri2", triOn(minus, [a / 2, (3 * a) / 4], 0)],
    ["tri3", triOn(minus, [a / 2, (3 * a) / 4], 2)],
  ];
  return template([3, 3, 4, 3, 4], a, a, polygons, { glide: true });
}

function snubhexTemplate(): ArchTemplate {
  // Snub hexagonal (3.3.3.3.6) on the rotated rectangle spanned by the
  // orthogonal superlattice vectors (5,1) and (3,-5): sqrt(7) x sqrt(21) edge
  // lengths holding two hexagons and sixteen triangles. Chiral (p6): no mirror.
  const width = Math.sqrt(7);
  const height = Math.sqrt(21);
  const uv = (x: number, row: number): Vertex => [
    (5 * x + 3 * row) / (4 * width),
    (3 * (x - 5 * row)) / (4 * height),
  ];
  const isHexCentre = (x: number, row: number): boolean => {
    const m = 3 * (x - 1) - row;
    const n = 5 * row - (x - 1);
    return m % 14 === 0 && n % 14 === 0;
  };
  const inDomain = (points: Vertex[]): boolean => {
    let cu = 0;
    let cv = 0;
    for (const [u, v] of points) {
      cu += u;
      cv += v;
    }
    cu /= points.length;
    cv /= points.length;
    return -1e-9 <= cu && cu < width - 1e-9 && -1e-9 <= cv && cv < height - 1e-9;
  };
  const polygons: [string, Vertex[]][] = [];
  for (let row = -7; row < 4; row++) {
    for (let i = -3; i < 11; i++) {
      const corners = triangleVertices(i, row, (row + i) % 2 === 0);
      if (corners.some(([x, r]) => isHexCentre(x, r))) continue; // part of a hexagon
      const points = corners.map(([x, r]) => uv(x, r));
      if (inDomain(points)) polygons.push([`t${row},${i}`, points]);
    }
  }
  const ring: [number, number][] = [[2, 0], [1, 1], [-1, 1], [-2, 0], [-1, -1], [1, -1]];
  for (let m = -3; m < 4; m++) {
    for (let n = -3; n < 4; n++) {
      const cx = 1 + 5 * m + n;
      const crow = m + 3 * n;
      const points = ring.map(([ox, oy]) => uv(cx + ox, crow + oy));
      if (inDomain(points)) polygons.push([`h${m},${n}`, points]);
    }
  }
  return template([3, 3, 3, 3, 6], width, height, polygons, { mirrored: false });
}

function trunchexTemplate(): ArchTemplate {
  // Truncated hexagonal (3.12.12): dodecagons on a hexagonal lattice of pitch
  // 2 + sqrt(3), up/down triangles between them.
  const a = 2 + ROOT3;
  const r = (Math.sqrt(6) + Math.SQRT2) / 2; // dodecagon circumradius, side 1
  const e = 0.5 + ROOT3 / 2;
  const around = (cx: number, cy: number, suffix: string): [string, Vertex[]][] => {
    const dodecagon: Vertex[] = [];
    for (let k = 0; k < 12; k++) {
      const ang = (15 + 30 * k) * DEG;
      dodecagon.push([cx + r * Math.cos(ang), cy + r * Math.sin(ang)]);
    }
    return [
      ["dod" + suffix, dodecagon],
      ["up" + suffix, [[cx + a / 2, cy + 0.5], [cx + a - e, cy + e], [cx + e, cy + e]]],
      ["down" + suffix, [[cx + a / 2, cy - 0.5], [cx + e, cy - e], [cx + a - e, cy - e]]],
    ];
  };
  const polygons = [...around(0, 0, "0"), ...around(a / 2, (a * ROOT3) / 2, "1")];
  return template([3, 12, 12], a, a * ROOT3, polygons);
}

function rhombitrihexTemplate(): ArchTemplate {
  // Rhombitrihexagonal (3.4.6.4): hexagons on a triangular lattice of pitch
  // 1 + sqrt(3), a square across every hexagon edge and a triangle in each gap.
  const a = 1 + ROOT3;
  const centreAt = (m: number, n: number): Vertex => [m * a + (n * a) / 2, (n * a * ROOT3) / 2];
  const hexagonAt = (cx: number, cy: number): Vertex[] => regularPolygon(cx, cy, 6, 1, 30);
  const decorate = (cx: number, cy: number): [string, Vertex[]][] => {
    const out: [string, Vertex[]][] = [];
    for (let k = 0; k < 6; k++) {
      out.push(["sq", squareOnEdge(cx, cy, ROOT3 / 2, 60 * k)]);
      const vx = cx + Math.cos((30 + 60 * k) * DEG);
      const vy = cy + Math.sin((30 + 60 * k) * DEG);
      const u1: Vertex = [Math.cos(60 * k * DEG), Math.sin(60 * k * DEG)];
      const u2: Vertex = [Math.cos((60 * k + 60) * DEG), Math.sin((60 * k + 60) * DEG)];
      out.push(["tri", [[vx, vy], [vx + u1[0], vy + u1[1]], [vx + u2[0], vy + u2[1]]]]);
    }
    return out;
  };
  const width = a;
  const height = a * ROOT3;
  return template([3, 4, 6, 4], width, height, hexLatticePolygons(centreAt, hexagonAt, decorate, width, height));
}

function trunctrihexTemplate(): ArchTemplate {
  // Truncated trihexagonal (4.6.12): dodecagons on a triangular lattice of pitch
  // 3 + sqrt(3), a square across every second edge and a hexagon in each gap.
  const a = 3 + ROOT3;
  const r12 = (Math.sqrt(6) + Math.SQRT2) / 2; // dodecagon circumradius, side 1
  const apothem = (2 + ROOT3) / 2;
  const centreAt = (m: number, n: number): Vertex => [m * a + (n * a) / 2, (n * a * ROOT3) / 2];
  const dodecagonAt = (cx: number, cy: number): Vertex[] => regularPolygon(cx, cy, 12, r12, 15);
  const decorate = (cx: number, cy: number): [string, Vertex[]][] => {
    // this dodecagon's lattice indices, to locate its triangular holes
    const n0 = Math.round(cy / ((a * ROOT3) / 2));
    const m0 = Math.round((cx - (n0 * a) / 2) / a);
    const out: [string, Vertex[]][] = [];
    for (let k = 0; k < 6; k++) out.push(["sq", squareOnEdge(cx, cy, apothem, 60 * k)]);
    const cornerSets: [number, number][][] = [
      [[0, 0], [1, 0], [0, 1]],
      [[1, 0], [0, 1], [1, 1]],
    ];
    for (const corners of cornerSets) {
      const centres = corners.map(([dm, dn]) => centreAt(m0 + dm, n0 + dn));
      let hx = 0;
      let hy = 0;
      for (const [x, y] of centres) {
        hx += x;
        hy += y;
      }
      out.push(["hex", regularPolygon(hx / 3, hy / 3, 6, 1, 0)]);
    }
    return out;
  };
  const width = a;
  const height = a * ROOT3;
  return template([4, 6, 12], width, height, hexLatticePolygons(centreAt, dodecagonAt, decorate, width, height));
}

// -- Laves (dual / Catalan) tilings ------------------------------------------
//
// Each Laves tiling is the dual of one Archimedean tiling: a vertex at every
// tile centre, joined across every shared edge. `dualTemplate` builds it
// mechanically from the primal template.

function dualTemplate(primal: () => ArchTemplate): ArchTemplate {
  const p = primal();
  const { width, height } = p;
  const centroidOf = (refs: Ref[]): Vertex => {
    let cx = 0;
    let cy = 0;
    for (const r of refs) {
      const v = p.verts.get(r.tag)!;
      cx += r.dm * width + v[0];
      cy += r.dn * height + v[1];
    }
    return [cx / refs.length, cy / refs.length];
  };
  const centres = new Map<string, Vertex>();
  const sides = new Map<string, number>();
  for (const { name, refs } of p.cells) {
    centres.set(name, centroidOf(refs));
    sides.set(name, refs.length);
  }

  // dual vertex = primal tile centre; dual face = the ring of tile centres
  // around a primal vertex, ordered by angle
  const polygons: [string, Vertex[]][] = [];
  let i = 0;
  for (const [vertex, [vx, vy]] of p.verts) {
    const ring: Vertex[] = [];
    for (const { name, refs } of p.cells) {
      const [cx, cy] = centres.get(name)!;
      for (const r of refs) {
        if (r.tag === vertex) ring.push([cx - r.dm * width, cy - r.dn * height]);
      }
    }
    ring.sort((a, b) => Math.atan2(a[1] - vy, a[0] - vx) - Math.atan2(b[1] - vy, b[0] - vx));
    polygons.push([`d${i}`, ring]);
    i++;
  }

  // centre the flat window on the primal's largest tile (its centre is the
  // highest-order rotation/mirror centre shared by both tilings)
  let widest = 0;
  for (const s of sides.values()) widest = Math.max(widest, s);
  let centre: Vertex | null = null;
  let best = Infinity;
  for (const [name, [cx, cy]] of centres) {
    if (sides.get(name) !== widest) continue;
    const wx = round6(((cx % width) + width) % width);
    const wy = round6(((cy % height) + height) % height);
    const d = wx * wx + wy * wy;
    if (d < best) {
      best = d;
      centre = [wx, wy];
    }
  }
  return template(p.config, width, height, polygons, {
    mirrored: p.mirror !== null,
    glide: p.glide,
    centre,
  });
}

// -- registry ----------------------------------------------------------------

export interface ArchTiling {
  key: string;
  label: string;
  config: number[];
  edgeDirections: number;
  template: () => ArchTemplate;
  vertexTransitive: boolean;
}

export const ARCH_TILINGS: ArchTiling[] = [
  { key: "elongated", label: "Elongated triangular", config: [3, 3, 3, 4, 4], edgeDirections: 12, template: elongatedTemplate, vertexTransitive: true },
  { key: "snubsquare", label: "Snub square", config: [3, 3, 4, 3, 4], edgeDirections: 12, template: snubsquareTemplate, vertexTransitive: true },
  { key: "kagome", label: "Kagome", config: [3, 6, 3, 6], edgeDirections: 12, template: kagomeTemplate, vertexTransitive: true },
  { key: "snubhex", label: "Snub hexagonal", config: [3, 3, 3, 3, 6], edgeDirections: 12, template: snubhexTemplate, vertexTransitive: true },
  { key: "truncsquare", label: "Truncated square", config: [4, 8, 8], edgeDirections: 8, template: truncsquareTemplate, vertexTransitive: true },
  { key: "trunchex", label: "Truncated hexagonal", config: [3, 12, 12], edgeDirections: 12, template: trunchexTemplate, vertexTransitive: true },
  { key: "rhombitrihex", label: "Rhombitrihexagonal", config: [3, 4, 6, 4], edgeDirections: 12, template: rhombitrihexTemplate, vertexTransitive: true },
  { key: "trunctrihex", label: "Truncated trihexagonal", config: [4, 6, 12], edgeDirections: 12, template: trunctrihexTemplate, vertexTransitive: true },
  // the Laves (dual / Catalan) tilings -- face-transitive
  { key: "prismaticpent", label: "Prismatic pentagonal", config: [3, 3, 3, 4, 4], edgeDirections: 12, template: () => dualTemplate(elongatedTemplate), vertexTransitive: false },
  { key: "cairo", label: "Cairo pentagonal", config: [3, 3, 4, 3, 4], edgeDirections: 12, template: () => dualTemplate(snubsquareTemplate), vertexTransitive: false },
  { key: "rhombille", label: "Rhombille", config: [3, 6, 3, 6], edgeDirections: 12, template: () => dualTemplate(kagomeTemplate), vertexTransitive: false },
  { key: "floret", label: "Floret pentagonal", config: [3, 3, 3, 3, 6], edgeDirections: 12, template: () => dualTemplate(snubhexTemplate), vertexTransitive: false },
  { key: "tetrakis", label: "Tetrakis square", config: [4, 8, 8], edgeDirections: 8, template: () => dualTemplate(truncsquareTemplate), vertexTransitive: false },
  { key: "triakis", label: "Triakis triangular", config: [3, 12, 12], edgeDirections: 12, template: () => dualTemplate(trunchexTemplate), vertexTransitive: false },
  { key: "deltoidal", label: "Deltoidal trihexagonal", config: [3, 4, 6, 4], edgeDirections: 12, template: () => dualTemplate(rhombitrihexTemplate), vertexTransitive: false },
  { key: "kisrhombille", label: "Kisrhombille", config: [4, 6, 12], edgeDirections: 12, template: () => dualTemplate(trunctrihexTemplate), vertexTransitive: false },
];

const ARCH_BY_KEY = new Map(ARCH_TILINGS.map((t) => [t.key, t]));
const TEMPLATE_CACHE = new Map<string, ArchTemplate>();

/** The memoized fundamental-domain template for a tiling key. */
export function archTemplate(tiling: string): ArchTemplate {
  let t = TEMPLATE_CACHE.get(tiling);
  if (!t) {
    const spec = ARCH_BY_KEY.get(tiling);
    if (!spec) throw new Error(`unknown tiling ${tiling}`);
    t = spec.template();
    TEMPLATE_CACHE.set(tiling, t);
  }
  return t;
}

/** A flat, roughly `nx` by `ny` domain rectangle of an Archimedean tiling,
 * built from the tiling's periodic domain (the same template that wraps the
 * donut/cylinder/Möbius/Klein). The window is centred on the larger tile
 * nearest the middle so the patch is symmetric under the tiling's point group. */
export function archimedeanBoard(
  tiling: string,
  nx: number,
  ny: number,
  mineCount: number,
  scale = 40,
): Board {
  const t = archTemplate(tiling);
  const W = t.width;
  const H = t.height;
  const position = (m: number, n: number, tag: string): Vertex => {
    const v = t.verts.get(tag)!;
    return [m * W + v[0], n * H + v[1]];
  };

  // grow two extra domains all round so the centred window is fully populated
  interface Grown {
    verts: { m: number; n: number; tag: string }[];
    centroid: Vertex;
    size: number;
  }
  const grown = new Map<CellId, Grown>();
  for (let m = 0; m < nx + 2; m++) {
    for (let n = 0; n < ny + 2; n++) {
      for (const { name, refs } of t.cells) {
        const verts = refs.map((r) => ({ m: m + r.dm, n: n + r.dn, tag: r.tag }));
        let cx = 0;
        let cy = 0;
        for (const v of verts) {
          const [x, y] = position(v.m, v.n, v.tag);
          cx += x;
          cy += y;
        }
        grown.set(cid(m, n, name), {
          verts,
          centroid: [cx / verts.length, cy / verts.length],
          size: verts.length,
        });
      }
    }
  }

  const midX = ((nx + 2) * W) / 2;
  const midY = ((ny + 2) * H) / 2;
  let cx0 = 0;
  let cy0 = 0;
  let best = Infinity;
  if (t.centre) {
    const [ccx, ccy] = t.centre;
    for (let m = 0; m < nx + 2; m++) {
      for (let n = 0; n < ny + 2; n++) {
        const x = ccx + m * W;
        const y = ccy + n * H;
        const d = (x - midX) ** 2 + (y - midY) ** 2;
        if (d < best) {
          best = d;
          cx0 = x;
          cy0 = y;
        }
      }
    }
  } else {
    let biggest = 0;
    for (const g of grown.values()) biggest = Math.max(biggest, g.size);
    for (const g of grown.values()) {
      if (g.size !== biggest) continue;
      const d = (g.centroid[0] - midX) ** 2 + (g.centroid[1] - midY) ** 2;
      if (d < best) {
        best = d;
        cx0 = g.centroid[0];
        cy0 = g.centroid[1];
      }
    }
  }

  const halfW = (nx * W) / 2;
  const halfH = (ny * H) / 2;
  const cells = new Map<CellId, string[]>();
  const positions = new Map<string, Vertex>();
  for (const [cell, g] of grown) {
    if (
      Math.abs(g.centroid[0] - cx0) <= halfW + 1e-9 &&
      Math.abs(g.centroid[1] - cy0) <= halfH + 1e-9
    ) {
      const keys = g.verts.map((v) => {
        const ks = `${v.m},${v.n},${v.tag}`;
        if (!positions.has(ks)) positions.set(ks, position(v.m, v.n, v.tag));
        return ks;
      });
      cells.set(cell, keys);
    }
  }
  return finalizeFlat(tiling, cells, positions, mineCount, scale);
}
