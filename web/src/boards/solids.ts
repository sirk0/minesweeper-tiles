// Port of minesweeper/boards/solids.py — the closed 3D boards (sphere family,
// fullerenes, cube, tetrahedra, frames). Structure and formulas are kept
// textually close to the Python so the two stay diffable; hashable tuple keys
// become canonical strings. Trig/last-ulp drift is far below the 1e-6
// quantization the topology helpers use.
import {
  cid,
  dot,
  isBoard3D,
  newellNormal,
  normalize,
  orientOutward,
  sharedVertexAdjacency,
  tangentOrder,
  type Board3D,
  type CellId,
  type Vec3,
} from "./core";

export { isBoard3D };

const ROOT3 = Math.sqrt(3);

type Positions = Map<string, Vec3>;
type Cells = Map<CellId, string[]>;

function gcdAll(values: number[]): number {
  let g = 0;
  for (let v of values) {
    v = Math.abs(v);
    while (v) [g, v] = [v, g % v];
  }
  return g;
}

function centroidOf(points: readonly Vec3[]): Vec3 {
  const c: Vec3 = [0, 0, 0];
  for (const p of points) {
    c[0] += p[0];
    c[1] += p[1];
    c[2] += p[2];
  }
  return [c[0] / points.length, c[1] / points.length, c[2] / points.length];
}

interface VertexFaces {
  vertices: Vec3[];
  faces: [number, number, number][];
}

function icosahedron(): VertexFaces {
  const phi = (1 + Math.sqrt(5)) / 2;
  const vertices: Vec3[] = [];
  for (const x of [-1, 1]) {
    for (const z of [-phi, phi]) {
      vertices.push([0, x, z], [x, z, 0], [z, 0, x]);
    }
  }
  // edges have squared length 4; faces are the 3-cliques of the edge graph
  const touching = (i: number, j: number): boolean => {
    const a = vertices[i]!;
    const b = vertices[j]!;
    const d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
    return Math.abs(d - 4) < 1e-9;
  };
  const faces: [number, number, number][] = [];
  for (let i = 0; i < 12; i++) {
    for (let j = i + 1; j < 12; j++) {
      if (!touching(i, j)) continue;
      for (let k = j + 1; k < 12; k++) {
        if (touching(i, k) && touching(j, k)) {
          // consistent winding: orient every face counterclockwise as seen
          // from outside
          const [a, b, c] = [vertices[i]!, vertices[j]!, vertices[k]!];
          const normal = newellNormal([a, b, c]);
          const outward =
            normal[0] * (a[0] + b[0] + c[0]) +
            normal[1] * (a[1] + b[1] + c[1]) +
            normal[2] * (a[2] + b[2] + c[2]);
          faces.push(outward > 0 ? [i, j, k] : [i, k, j]);
        }
      }
    }
  }
  if (faces.length !== 20) throw new Error("icosahedron faces != 20");
  return { vertices, faces };
}

/** A regular tetrahedron: four vertices on alternate cube corners, the four
 * faces being the four vertex triples. Winding is arbitrary (each subdivided
 * cell is re-oriented outward on assembly). */
function tetrahedron(): VertexFaces {
  const vertices: Vec3[] = [
    [1, 1, 1],
    [1, -1, -1],
    [-1, 1, -1],
    [-1, -1, 1],
  ];
  const faces: [number, number, number][] = [
    [1, 2, 3],
    [0, 2, 3],
    [0, 1, 3],
    [0, 1, 2],
  ];
  return { vertices, faces };
}

/** Assemble a closed convex board, orienting each polygon outward by its
 * centroid direction. Correct for any convex solid that contains the origin
 * (sphere, cube, tetrahedron): every surface point has a positive dot with
 * its face's outward normal. */
function convexBoard3d(
  mode: string,
  cells: Cells,
  positions: Positions,
  mineCount: number,
  radius = 1,
): Board3D {
  const adjacency = sharedVertexAdjacency(cells);
  const polygons = new Map<CellId, Vec3[]>();
  for (const [cell, keys] of cells) {
    const polygon = keys.map((key) => positions.get(key)!);
    polygons.set(cell, orientOutward(polygon, centroidOf(polygon)));
  }
  return {
    mode,
    polygons,
    adjacency,
    mineCount,
    radius,
    twoSided: false,
    cellCycle: null,
  };
}

// -- 3D builders --------------------------------------------------------------

/** The pentagonal hexecontahedron as (cells, vertex positions): the Conway
 * "gyro" operation on an icosahedron — each triangular face gains a center
 * vertex, each edge two division points, and every (face, corner) pair
 * becomes one pentagon. */
function gyroPentagons(): { cells: Cells; positions: Positions } {
  const { vertices, faces } = icosahedron();
  const positions: Positions = new Map();

  const vertexKey = (i: number): string => {
    const key = cid("v", i);
    positions.set(key, normalize(vertices[i]!));
    return key;
  };

  const edgeKey = (u: number, v: number, third: number): string => {
    // point at u + third/3 of the way to v; same point seen from the other
    // end is (v, u, 3 - third)
    const key = u < v ? cid("e", u, v, third) : cid("e", v, u, 3 - third);
    const a = vertices[u]!;
    const b = vertices[v]!;
    positions.set(
      key,
      normalize([
        a[0] + ((b[0] - a[0]) * third) / 3,
        a[1] + ((b[1] - a[1]) * third) / 3,
        a[2] + ((b[2] - a[2]) * third) / 3,
      ]),
    );
    return key;
  };

  const cells: Cells = new Map();
  faces.forEach((face, faceIndex) => {
    const centerKey = cid("c", faceIndex);
    positions.set(
      centerKey,
      normalize(centroidOf(face.map((i) => vertices[i]!))),
    );
    for (let i = 0; i < 3; i++) {
      const u = face[(i + 2) % 3]!;
      const v = face[i]!;
      const w = face[(i + 1) % 3]!;
      cells.set(cid(faceIndex, i), [
        centerKey,
        edgeKey(u, v, 2),
        vertexKey(v),
        edgeKey(v, w, 1),
        edgeKey(v, w, 2),
      ]);
    }
  });
  return { cells, positions };
}

/** A sphere tiled with 60 pentagons (a pentagonal hexecontahedron, projected
 * onto the unit sphere). Every pentagon has exactly 7 neighbors. */
export function sphereBoard(mineCount: number): Board3D {
  const { cells, positions } = gyroPentagons();
  return convexBoard3d("sphere", cells, positions, mineCount);
}

/** A snub dodecahedron: 12 pentagons and 80 triangles (vertex configuration
 * 3.3.3.3.5), projected onto the unit sphere. Built as the dual of the
 * pentagonal hexecontahedron: one cell per hexecontahedron vertex, made of
 * the surrounding pentagon centers. */
export function snubDodecahedronBoard(mineCount: number): Board3D {
  const { cells: pentagons, positions } = gyroPentagons();
  const centers: Positions = new Map();
  for (const [cellId, keys] of pentagons) {
    centers.set(
      cellId,
      normalize(centroidOf(keys.map((k) => positions.get(k)!))),
    );
  }
  const around = new Map<string, CellId[]>();
  for (const [cellId, keys] of pentagons) {
    for (const key of keys) {
      let ids = around.get(key);
      if (!ids) around.set(key, (ids = []));
      ids.push(cellId);
    }
  }
  const cells: Cells = new Map();
  for (const [key, ids] of around) {
    cells.set(
      key,
      tangentOrder(
        positions.get(key)!,
        ids.map((cellId) => [cellId, centers.get(cellId)!]),
      ),
    );
  }
  return convexBoard3d("snubdodec", cells, centers, mineCount);
}

/** Subdivide each triangular face into `frequency**2` triangles. Defaults to
 * the icosahedron; `project` normalizes vertices onto the unit sphere (a
 * geodesic icosahedron), otherwise they stay on the flat faces (e.g. a
 * triangulated tetrahedron).
 *
 * Returns (positions, triangles). Vertex keys are gcd-normalized barycentric
 * weights over the corners, so vertices on shared edges match exactly across
 * faces. */
function geodesic(
  frequency: number,
  base?: VertexFaces,
  project = true,
): { positions: Positions; triangles: string[][] } {
  const { vertices, faces } = base ?? icosahedron();
  const positions: Positions = new Map();
  const triangles: string[][] = [];
  for (const face of faces) {
    const corners = face.map((v) => vertices[v]!);

    const key = (i: number, j: number): string => {
      const weights = [frequency - i - j, i, j];
      const items: [number, number][] = [];
      for (let n = 0; n < 3; n++) {
        if (weights[n]! > 0) items.push([face[n]!, weights[n]!]);
      }
      const g = gcdAll(items.map(([, w]) => w));
      const vertexKey = items
        .map(([v, w]) => [v, w / g] as [number, number])
        .sort((a, b) => a[0] - b[0] || a[1] - b[1])
        .map(([v, w]) => `${v}:${w}`)
        .join("|");
      if (!positions.has(vertexKey)) {
        const point: Vec3 = [0, 1, 2].map(
          (axis) =>
            (weights[0]! * corners[0]![axis]! +
              weights[1]! * corners[1]![axis]! +
              weights[2]! * corners[2]![axis]!) /
            frequency,
        ) as Vec3;
        positions.set(vertexKey, project ? normalize(point) : point);
      }
      return vertexKey;
    };

    for (let i = 0; i < frequency; i++) {
      for (let j = 0; j < frequency - i; j++) {
        triangles.push([key(i, j), key(i + 1, j), key(i, j + 1)]);
        if (i + j < frequency - 1) {
          triangles.push([key(i + 1, j), key(i + 1, j + 1), key(i, j + 1)]);
        }
      }
    }
  }
  return { positions, triangles };
}

/** The dual of a geodesic icosahedron: one cell per geodesic vertex, made of
 * the surrounding triangle centers. Always 12 pentagons plus
 * `10 * frequency**2 - 10` hexagons. */
function goldbergBoard(
  mode: string,
  frequency: number,
  mineCount: number,
): Board3D {
  const { positions, triangles } = geodesic(frequency);
  const centers: Positions = new Map();
  const around = new Map<string, string[]>();
  for (const triangle of triangles) {
    const triangleId = [...triangle].sort().join(";");
    centers.set(
      triangleId,
      normalize(centroidOf(triangle.map((k) => positions.get(k)!))),
    );
    for (const key of triangle) {
      let ids = around.get(key);
      if (!ids) around.set(key, (ids = []));
      ids.push(triangleId);
    }
  }
  const cells: Cells = new Map();
  for (const [key, triangleIds] of around) {
    const ring: [string, Vec3][] = triangleIds.map((tid) => [
      tid,
      centers.get(tid)!,
    ]);
    cells.set(key, tangentOrder(positions.get(key)!, ring));
  }
  return convexBoard3d(mode, cells, centers, mineCount);
}

/** A C80 fullerene (chamfered dodecahedron): 12 pentagons and 30 hexagons,
 * projected onto the unit sphere. */
export function c80Board(mineCount: number): Board3D {
  return goldbergBoard("c80", 2, mineCount);
}

/** A C180 fullerene (Goldberg GP(3,0)): 12 pentagons and 80 hexagons,
 * projected onto the unit sphere. */
export function c180Board(mineCount: number): Board3D {
  return goldbergBoard("c180", 3, mineCount);
}

/** A sphere tiled with triangles: a geodesic icosahedron with
 * `20 * frequency**2` triangular cells. */
export function sphereTriangleBoard(mineCount: number, frequency = 2): Board3D {
  const { positions, triangles } = geodesic(frequency);
  const cells: Cells = new Map();
  triangles.forEach((triangle, n) => cells.set(cid("t", n), [...triangle]));
  return convexBoard3d("spheretri", cells, positions, mineCount);
}

/** A cube surface tiled with `6 * n**2` squares: each face an n x n grid.
 * Vertices are integer points on `[-n, n]**3` (a surface vertex has one axis
 * at +-n; the grid lines step by 2), so cells on adjacent faces sharing a
 * cube edge or corner become neighbors automatically. */
export function cubeBoard(n: number, mineCount: number): Board3D {
  const cells: Cells = new Map();
  const positions: Positions = new Map();
  for (let axis = 0; axis < 3; axis++) {
    const [uAxis, vAxis] = [0, 1, 2].filter((a) => a !== axis) as [
      number,
      number,
    ];
    for (const sign of [-1, 1]) {
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          const keys: string[] = [];
          for (const [du, dv] of [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
          ] as const) {
            const coord: [number, number, number] = [0, 0, 0];
            coord[axis] = sign * n;
            coord[uAxis] = -n + 2 * (i + du);
            coord[vAxis] = -n + 2 * (j + dv);
            const key = cid(...coord);
            keys.push(key);
            if (!positions.has(key)) {
              positions.set(key, [coord[0] / n, coord[1] / n, coord[2] / n]);
            }
          }
          cells.set(cid(axis, sign, i, j), keys);
        }
      }
    }
  }
  return convexBoard3d("cube", cells, positions, mineCount, ROOT3);
}

/** The boundary of a polycube (a union of axis-aligned unit cubes), tiled by
 * unit squares. `solid(i, j, k)` says whether the unit cube at integer
 * indices is filled; `extent` is the `(nx, ny, nz)` bounding box. Cubes are
 * scaled uniformly and centered in `[-1, 1]`.
 *
 * A unit square is a cell exactly when it separates a filled cube from empty
 * space, and it is wound so its normal points outward (out of the filled
 * cube) — which, unlike the centroid rule `convexBoard3d` uses, is also
 * correct for the concave step shoulders and inner walls these solids have.
 * Vertices are the integer lattice points, so faces meeting at an edge or
 * corner share vertex ids and become neighbors. */
function polycubeSurface(
  mode: string,
  solid: (i: number, j: number, k: number) => boolean,
  extent: [number, number, number],
  mineCount: number,
): Board3D {
  const [nx, ny, nz] = extent;
  const center: Vec3 = [nx / 2, ny / 2, nz / 2];
  const scale = 2 / Math.max(nx, ny, nz);

  const position = (p: readonly number[]): Vec3 => [
    (p[0]! - center[0]) * scale,
    (p[1]! - center[1]) * scale,
    (p[2]! - center[2]) * scale,
  ];

  const filled = (i: number, j: number, k: number): boolean =>
    i >= 0 && i < nx && j >= 0 && j < ny && k >= 0 && k < nz && solid(i, j, k);

  const cells: Cells = new Map();
  const positions: Positions = new Map();
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < ny; j++) {
      for (let k = 0; k < nz; k++) {
        if (!solid(i, j, k)) continue;
        for (let axis = 0; axis < 3; axis++) {
          for (const sign of [-1, 1]) {
            const step = [0, 0, 0];
            step[axis] = sign;
            if (filled(i + step[0]!, j + step[1]!, k + step[2]!)) {
              continue; // interior face, not on the boundary
            }
            const base = [i, j, k];
            if (sign > 0) base[axis]! += 1; // the far face of the cube
            const [uAxis, vAxis] = [0, 1, 2].filter((a) => a !== axis) as [
              number,
              number,
            ];
            let corners: number[][] = [];
            for (const [du, dv] of [
              [0, 0],
              [1, 0],
              [1, 1],
              [0, 1],
            ] as const) {
              const p = [...base];
              p[uAxis]! += du;
              p[vAxis]! += dv;
              corners.push(p);
            }
            const outward: Vec3 = [0, 0, 0];
            outward[axis] = sign;
            const pts = corners.map(position);
            if (dot(newellNormal(pts), outward) <= 0) {
              corners = corners.reverse();
            }
            const keys: string[] = [];
            for (const p of corners) {
              const key = cid(...(p as [number, number, number]));
              keys.push(key);
              if (!positions.has(key)) positions.set(key, position(p));
            }
            cells.set(cid(i, j, k, axis, sign), keys);
          }
        }
      }
    }
  }
  let radius = 0;
  for (const p of positions.values()) {
    radius = Math.max(radius, Math.hypot(p[0], p[1], p[2]));
  }
  // Closed but non-convex: each cell is already wound outward by the builder
  // (its outward normal is known from which cube face it is), so — unlike
  // convexBoard3d — orientation is not inferred from the centroid direction,
  // which is wrong for the inward-facing tunnel walls.
  const adjacency = sharedVertexAdjacency(cells);
  const polygons = new Map<CellId, Vec3[]>();
  for (const [cell, keys] of cells) {
    polygons.set(
      cell,
      keys.map((key) => positions.get(key)!),
    );
  }
  return {
    mode,
    polygons,
    adjacency,
    mineCount,
    radius,
    twoSided: false,
    cellCycle: null,
  };
}

/** The surface of a cube frame (a level-1 Menger sponge): an `n x n x n`
 * stack of unit cubes with an `(n - 2*thickness)` cube bored out of the
 * middle of each face, meeting in a hollow centre. What is left are the
 * twelve edge bars plus eight corners — a genus-5 solid whose whole boundary
 * is tiled by unit squares.
 *
 * A unit cube is kept when at least two of its three coordinates lie in the
 * outer band (within `thickness` of a face). */
export function cubeFrameBoard(
  n: number,
  thickness: number,
  mineCount: number,
): Board3D {
  if (!(thickness >= 1 && 2 * thickness < n)) {
    throw new Error("thickness must be >= 1 and leave a non-empty hole");
  }
  const outer = (c: number): boolean => c < thickness || c >= n - thickness;
  const solid = (i: number, j: number, k: number): boolean =>
    Number(outer(i)) + Number(outer(j)) + Number(outer(k)) >= 2;
  return polycubeSurface("cubeframe", solid, [n, n, n], mineCount);
}

/** A stepped bipyramid: a stepped pyramid of square terraces stitched
 * base-to-base with its z-mirror image (the shared biggest terrace kept only
 * once). Square layer `d` steps from the middle has side `base - 2*d`, so
 * the solid is widest at the equator and tapers to a small square top and
 * bottom — a terraced diamond whose staircase surface (concave at every
 * shoulder) is tiled by unit squares.
 *
 * `levels` counts the terraces of one pyramid; the apex square has side
 * `base - 2*(levels - 1)` and the whole stack is `2*levels - 1` layers
 * tall. */
export function steppedBipyramidBoard(
  base: number,
  levels: number,
  mineCount: number,
): Board3D {
  if (!(levels >= 2 && base - 2 * (levels - 1) >= 1)) {
    throw new Error("need levels >= 2 and a positive apex square");
  }
  const height = 2 * levels - 1;
  const middle = levels - 1; // the z-index of the biggest (equator) terrace
  const solid = (i: number, j: number, k: number): boolean => {
    const margin = Math.abs(k - middle); // each step in shrinks by 1
    return margin <= i && i < base - margin && margin <= j && j < base - margin;
  };
  return polycubeSurface(
    "steppedbipyramid",
    solid,
    [base, base, height],
    mineCount,
  );
}

/** A regular tetrahedron tiled with triangles: each of the 4 faces
 * subdivided into `frequency**2` cells, kept flat on the faces. */
export function tetrahedronBoard(mineCount: number, frequency = 4): Board3D {
  const { positions, triangles } = geodesic(frequency, tetrahedron(), false);
  const cells: Cells = new Map();
  triangles.forEach((triangle, n) => cells.set(cid("t", n), [...triangle]));
  let radius = 0;
  for (const p of positions.values()) {
    radius = Math.max(radius, Math.hypot(p[0], p[1], p[2]));
  }
  return convexBoard3d("tetrahedron", cells, positions, mineCount, radius);
}

/** A level-1 Sierpiński tetrahedron: midpoint-subdividing a regular
 * tetrahedron splits it into four corner sub-tetrahedra plus a central
 * octahedron, and the octahedron is carved out. What is left are the four
 * half-scale corner tetrahedra, meeting only at the six edge-midpoints of
 * the original — so on each original face the middle triangle is gone. Each
 * sub-tetrahedron face is subdivided into `frequency**2` flat triangles.
 *
 * Non-convex (the inward faces point toward the hollow centre), so unlike
 * `tetrahedronBoard` each triangle is oriented outward from its own
 * sub-tetrahedron's centroid rather than the origin. */
export function tetrahedronFrameBoard(
  mineCount: number,
  frequency = 4,
): Board3D {
  const { vertices: base } = tetrahedron();
  // Ten shared points: the 4 original corners, then the 6 edge midpoints.
  // A single global vertex list keeps the midpoints' subdivision keys
  // identical across the two sub-tetrahedra that meet at them.
  const verts: Vec3[] = [...base];
  const midIndex = new Map<string, number>();
  for (let a = 0; a < 4; a++) {
    for (let b = a + 1; b < 4; b++) {
      midIndex.set(`${a},${b}`, verts.length);
      verts.push([
        (base[a]![0] + base[b]![0]) / 2,
        (base[a]![1] + base[b]![1]) / 2,
        (base[a]![2] + base[b]![2]) / 2,
      ]);
    }
  }

  const cells: Cells = new Map();
  const positions: Positions = new Map();
  const centroids = new Map<CellId, Vec3>();
  for (let corner = 0; corner < 4; corner++) {
    const others = [0, 1, 2, 3].filter((j) => j !== corner);
    const tet = [
      corner,
      ...others.map((j) => midIndex.get(`${Math.min(corner, j)},${Math.max(corner, j)}`)!),
    ];
    const centroid = centroidOf(tet.map((v) => verts[v]!));
    const faces: [number, number, number][] = [
      [tet[1]!, tet[2]!, tet[3]!],
      [tet[0]!, tet[2]!, tet[3]!],
      [tet[0]!, tet[1]!, tet[3]!],
      [tet[0]!, tet[1]!, tet[2]!],
    ];
    const { positions: pos, triangles } = geodesic(
      frequency,
      { vertices: verts, faces },
      false,
    );
    for (const [k, v] of pos) positions.set(k, v);
    triangles.forEach((triangle, n) => {
      const cell = cid(corner, n);
      cells.set(cell, [...triangle]);
      centroids.set(cell, centroid);
    });
  }

  const adjacency = sharedVertexAdjacency(cells);
  const polygons = new Map<CellId, Vec3[]>();
  for (const [cell, keys] of cells) {
    const polygon = keys.map((key) => positions.get(key)!);
    const faceCentroid = centroidOf(polygon);
    const cc = centroids.get(cell)!;
    const outward: Vec3 = [
      faceCentroid[0] - cc[0],
      faceCentroid[1] - cc[1],
      faceCentroid[2] - cc[2],
    ];
    polygons.set(cell, orientOutward(polygon, outward));
  }
  let radius = 0;
  for (const p of positions.values()) {
    radius = Math.max(radius, Math.hypot(p[0], p[1], p[2]));
  }
  return {
    mode: "tetraframe",
    polygons,
    adjacency,
    mineCount,
    radius,
    twoSided: false,
    cellCycle: null,
  };
}
