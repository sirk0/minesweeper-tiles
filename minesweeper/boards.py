"""Board geometry: flat tilings (squares, triangles, hexagons) and 3D
surfaces (spheres, fullerenes, a donut, a Möbius strip, a cylinder).

Every board is a set of polygonal cells. Cell vertices are generated
with exact, hashable ids (integer lattice points in 2D, symbolic keys
in 3D), so cells that touch can be matched exactly: two cells are
neighbors when they share at least one vertex.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable

Cell = Hashable
LatticePoint = tuple[int, int]
Vec3 = tuple[float, float, float]

ROOT3 = 3**0.5

DIFFICULTIES = ("easy", "medium", "hard")

MODE_LABELS = {
    "square": "Squares",
    "triangle": "Triangle of triangles",
    "trigrid": "Triangle grid",
    "hex": "Hexagons",
    "hexhex": "Hexagon of hexagons",
    "penrose": "Penrose rhombi",
    "sphere": "60 pentagons",
    "c80": "C80 fullerene",
    "c180": "C180 fullerene",
    "spheretri": "Triangles",
    "torus": "Squares",
    "torustri": "Triangles",
    "torushex": "Hexagons",
    "mobius": "Squares",
    "mobiustri": "Triangles",
    "mobiushex": "Hexagons",
    "cylinder": "Squares",
    "cyltri": "Triangles",
    "cylhex": "Hexagons",
}

# The menu picks a topology first, then one of its tilings. A sphere
# cannot be tiled with hexagons alone (Euler's formula forces 12
# pentagons in), so the sphere offers fullerenes instead.
TOPOLOGIES = {
    "flat": ("Flat surface", ("square", "triangle", "trigrid", "hex", "hexhex", "penrose")),
    "sphere": ("Sphere", ("sphere", "c80", "c180", "spheretri")),
    "torus": ("Donut", ("torus", "torustri", "torushex")),
    "mobius": ("Möbius strip", ("mobius", "mobiustri", "mobiushex")),
    "cylinder": ("Cylinder", ("cylinder", "cyltri", "cylhex")),
}

MODES_3D = frozenset(
    {
        "sphere", "c80", "c180", "spheretri",
        "torus", "torustri", "torushex",
        "mobius", "mobiustri", "mobiushex",
        "cylinder", "cyltri", "cylhex",
    }
)


@dataclass(frozen=True)
class Board:
    mode: str
    polygons: dict[Cell, list[tuple[float, float]]]  # pixel-space vertices
    adjacency: dict[Cell, tuple[Cell, ...]]
    mine_count: int
    width: float
    height: float


@dataclass(frozen=True)
class Board3D:
    mode: str
    polygons: dict[Cell, list[Vec3]]  # vertices on the surface, origin-centered
    adjacency: dict[Cell, tuple[Cell, ...]]
    mine_count: int
    radius: float  # max vertex distance from the origin
    two_sided: bool = False  # open/non-orientable surfaces show both sides


def _shared_vertex_adjacency(cells: dict[Cell, list]) -> dict[Cell, tuple[Cell, ...]]:
    by_vertex: dict[Hashable, list[Cell]] = defaultdict(list)
    for cell, vertices in cells.items():
        for vertex in vertices:
            by_vertex[vertex].append(cell)
    touching: dict[Cell, set[Cell]] = {cell: set() for cell in cells}
    for group in by_vertex.values():
        for cell in group:
            touching[cell].update(group)
    return {cell: tuple(sorted(others - {cell})) for cell, others in touching.items()}


def _build(
    mode: str,
    lattice_cells: dict[Cell, list[LatticePoint]],
    unit: tuple[float, float],
    mine_count: int,
) -> Board:
    if not lattice_cells:
        raise ValueError("board has no cells")
    adjacency = _shared_vertex_adjacency(lattice_cells)
    ux, uy = unit
    polygons = {
        cell: [(kx * ux, ky * uy) for kx, ky in vertices]
        for cell, vertices in lattice_cells.items()
    }
    width = max(x for polygon in polygons.values() for x, _ in polygon)
    height = max(y for polygon in polygons.values() for _, y in polygon)
    return Board(mode, polygons, adjacency, mine_count, width, height)


# -- 2D builders (cells keyed by (row, index)) ------------------------------


def square_board(rows: int, cols: int, mine_count: int, scale: float = 32) -> Board:
    cells = {
        (r, c): [(c, r), (c + 1, r), (c + 1, r + 1), (c, r + 1)]
        for r in range(rows)
        for c in range(cols)
    }
    return _build("square", cells, (scale, scale), mine_count)


def _triangle_vertices(x: int, row: int, up: bool) -> list[LatticePoint]:
    """A unit triangle spanning lattice x..x+2 within lattice row ``row``.

    The lattice x unit is half a triangle side; the y unit is the
    triangle height.
    """
    if up:
        return [(x, row + 1), (x + 2, row + 1), (x + 1, row)]
    return [(x, row), (x + 2, row), (x + 1, row + 1)]


def triangle_board(size: int, mine_count: int, scale: float = 52) -> Board:
    """An equilateral triangle of side ``size`` subdivided into ``size**2``
    unit triangles. Row r holds 2r+1 alternating up/down triangles."""
    cells = {}
    for r in range(size):
        x_start = size - r - 1  # center each row
        for i in range(2 * r + 1):
            cells[(r, i)] = _triangle_vertices(x_start + i, r, up=i % 2 == 0)
    return _build("triangle", cells, (scale / 2, scale * ROOT3 / 2), mine_count)


def triangle_grid_board(
    rows: int, row_width: int, mine_count: int, scale: float = 52
) -> Board:
    """A rectangular strip surface: ``rows`` rows of ``row_width``
    alternating up/down triangles."""
    cells = {}
    for r in range(rows):
        for i in range(row_width):
            cells[(r, i)] = _triangle_vertices(i, r, up=(r + i) % 2 == 0)
    return _build("trigrid", cells, (scale / 2, scale * ROOT3 / 2), mine_count)


_HEX_VERTEX_OFFSETS = [(0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1)]


def hex_board(rows: int, cols: int, mine_count: int, scale: float = 20) -> Board:
    """Pointy-top hexagons in odd-r offset layout; ``scale`` is the hexagon
    circumradius. Lattice units: x = sqrt(3)/2 * scale, y = scale / 2."""
    cells = {}
    for r in range(rows):
        for c in range(cols):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            cells[(r, c)] = [(kx + ox, ky + oy) for ox, oy in _HEX_VERTEX_OFFSETS]
    return _build("hex", cells, (scale * ROOT3 / 2, scale / 2), mine_count)


def hexhex_board(radius: int, mine_count: int, scale: float = 20) -> Board:
    """A big hexagon composed of small hexagons: all axial coordinates
    (q, r) within ``radius`` of the center, 3r^2 + 3r + 1 cells."""
    cells = {}
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            kx = 2 * q + r + 2 * radius + 1
            ky = 3 * r + 3 * radius + 2
            cells[(q, r)] = [(kx + ox, ky + oy) for ox, oy in _HEX_VERTEX_OFFSETS]
    return _build("hexhex", cells, (scale * ROOT3 / 2, scale / 2), mine_count)


# -- Penrose tiling (P3, rhombi) ---------------------------------------------
#
# Vertices are exact elements of Z[zeta], zeta = exp(i*pi/5), stored as 4
# integer coefficients over the basis (1, z, z^2, z^3) with the reduction
# z^4 = -1 + z - z^2 + z^3. Robinson-triangle deflation only ever needs
# addition, subtraction and division by phi -- and 1/phi = phi - 1 =
# z^2 - z^3, so every operation stays in integers and vertex keys are
# exact: the shared-vertex adjacency needs no floating-point tolerance.

ZPoint = tuple[int, int, int, int]


def _zeta_mul(p: ZPoint) -> ZPoint:
    a, b, c, d = p
    return (-d, a + d, b - d, c + d)


def _z_add(p: ZPoint, q: ZPoint) -> ZPoint:
    return tuple(x + y for x, y in zip(p, q))


def _z_sub(p: ZPoint, q: ZPoint) -> ZPoint:
    return tuple(x - y for x, y in zip(p, q))


def _z_div_phi(p: ZPoint) -> ZPoint:
    z2 = _zeta_mul(_zeta_mul(p))
    return _z_sub(z2, _zeta_mul(z2))


_ZETA_BASIS = [
    (math.cos(math.pi * k / 5), math.sin(math.pi * k / 5)) for k in range(4)
]


def _z_to_xy(p: ZPoint) -> tuple[float, float]:
    return (
        sum(c * bx for c, (bx, _) in zip(p, _ZETA_BASIS)),
        sum(c * by for c, (_, by) in zip(p, _ZETA_BASIS)),
    )


def penrose_board(subdivisions: int, mine_count: int, scale: float = 300) -> Board:
    """An aperiodic Penrose tiling (P3): thick and thin rhombi.

    Starts from a wheel of ten half-rhombus Robinson triangles and
    deflates ``subdivisions`` times; mirror-image triangle halves are
    then merged into rhombi (unpaired halves on the outer rim are
    dropped). ``scale`` is the wheel radius in pixels.
    """
    zero = (0, 0, 0, 0)
    powers = [(1, 0, 0, 0)]
    for _ in range(10):
        powers.append(_zeta_mul(powers[-1]))

    # (color, apex, base1, base2): color 0 = half-thin, 1 = half-thick
    # (thick rhombi outnumber thin ones by phi in the limit)
    triangles = []
    for i in range(10):
        b, c = powers[i], powers[i + 1]
        if i % 2:
            b, c = c, b  # alternate handedness so mirror halves pair up
        triangles.append((0, zero, b, c))

    for _ in range(subdivisions):
        deflated = []
        for color, a, b, c in triangles:
            if color == 0:
                p = _z_add(a, _z_div_phi(_z_sub(b, a)))
                deflated += [(0, c, p, b), (1, p, c, a)]
            else:
                q = _z_add(b, _z_div_phi(_z_sub(a, b)))
                r = _z_add(b, _z_div_phi(_z_sub(c, b)))
                deflated += [(1, r, c, a), (1, q, r, b), (0, r, q, a)]
        triangles = deflated

    # merge mirror halves: partners share the color and the base edge
    waiting: dict = {}
    cells: dict[Cell, list[ZPoint]] = {}
    for color, a, b, c in triangles:
        key = (color, *sorted((b, c)))
        if key in waiting:
            other_apex = waiting.pop(key)
            cells[(color, len(cells))] = [a, b, other_apex, c]
        else:
            waiting[key] = a

    adjacency = _shared_vertex_adjacency(cells)
    xy = {
        key: _z_to_xy(key)
        for quad in cells.values()
        for key in quad
    }
    min_x = min(x for x, _ in xy.values())
    min_y = min(y for _, y in xy.values())
    polygons = {
        cell: [((x - min_x) * scale, (y - min_y) * scale) for x, y in (xy[k] for k in quad)]
        for cell, quad in cells.items()
    }
    width = max(x for polygon in polygons.values() for x, _ in polygon)
    height = max(y for polygon in polygons.values() for _, y in polygon)
    return Board("penrose", polygons, adjacency, mine_count, width, height)


# -- 3D helpers --------------------------------------------------------------


def _normalize(v: Vec3) -> Vec3:
    length = math.hypot(*v)
    return (v[0] / length, v[1] / length, v[2] / length)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def newell_normal(points: list[Vec3]) -> Vec3:
    """Normal of a (near-)planar 3D polygon, right-hand rule."""
    nx = ny = nz = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return (nx, ny, nz)


def _orient_outward(polygon: list[Vec3], outward: Vec3) -> list[Vec3]:
    """Order vertices counterclockwise as seen from outside the surface."""
    normal = newell_normal(polygon)
    return polygon if _dot(normal, outward) > 0 else list(reversed(polygon))


def _tangent_order(center: Vec3, items: list[tuple[Hashable, Vec3]]) -> list:
    """Order (key, position) pairs by angle around ``center`` (for points
    lying roughly on a circle around it, e.g. on a sphere)."""
    n = _normalize(center)
    reference = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    a = _normalize(_cross(n, reference))
    b = _cross(n, a)

    def angle(position: Vec3) -> float:
        d = tuple(p - c for p, c in zip(position, center))
        return math.atan2(_dot(d, b), _dot(d, a))

    return [key for key, _ in sorted(items, key=lambda item: angle(item[1]))]


def _icosahedron() -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    phi = (1 + 5**0.5) / 2
    vertices: list[Vec3] = []
    for x in (-1.0, 1.0):
        for z in (-phi, phi):
            vertices.append((0.0, x, z))
            vertices.append((x, z, 0.0))
            vertices.append((z, 0.0, x))
    # edges have squared length 4; faces are the 3-cliques of the edge graph
    def touching(i: int, j: int) -> bool:
        d = sum((a - b) ** 2 for a, b in zip(vertices[i], vertices[j]))
        return abs(d - 4.0) < 1e-9

    faces = []
    for i in range(12):
        for j in range(i + 1, 12):
            if not touching(i, j):
                continue
            for k in range(j + 1, 12):
                if touching(i, k) and touching(j, k):
                    # consistent winding: orient every face counterclockwise
                    # as seen from outside
                    a, b, c = (vertices[n] for n in (i, j, k))
                    normal = newell_normal([a, b, c])
                    outward = sum(n * (pa + pb + pc) for n, pa, pb, pc in zip(normal, a, b, c))
                    faces.append((i, j, k) if outward > 0 else (i, k, j))
    assert len(faces) == 20
    return vertices, faces


def _sphere_board3d(mode: str, cells, positions, mine_count: int) -> Board3D:
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        polygons[cell] = _orient_outward(polygon, centroid)
    return Board3D(mode, polygons, adjacency, mine_count, radius=1.0)


# -- 3D builders --------------------------------------------------------------


def sphere_board(mine_count: int) -> Board3D:
    """A sphere tiled with 60 pentagons (a pentagonal hexecontahedron,
    projected onto the unit sphere).

    Built with the Conway "gyro" operation on an icosahedron: each
    triangular face gains a center vertex, each edge two division
    points, and every (face, corner) pair becomes one pentagon. Every
    pentagon has exactly 7 neighbors.
    """
    vertices, faces = _icosahedron()
    positions: dict[Hashable, Vec3] = {}

    def vertex_key(i: int):
        key = ("v", i)
        positions[key] = _normalize(vertices[i])
        return key

    def edge_key(u: int, v: int, third: int):
        # point at u + third/3 of the way to v; same point seen from the
        # other end is (v, u, 3 - third)
        key = ("e", u, v, third) if u < v else ("e", v, u, 3 - third)
        a, b = vertices[u], vertices[v]
        positions[key] = _normalize(
            tuple(pa + (pb - pa) * third / 3 for pa, pb in zip(a, b))
        )
        return key

    cells: dict[Cell, list] = {}
    for face_index, face in enumerate(faces):
        center_key = ("c", face_index)
        positions[center_key] = _normalize(
            tuple(sum(vertices[i][axis] for i in face) / 3 for axis in range(3))
        )
        for i in range(3):
            u, v, w = face[i - 1], face[i], face[(i + 1) % 3]
            cells[(face_index, i)] = [
                center_key,
                edge_key(u, v, 2),
                vertex_key(v),
                edge_key(v, w, 1),
                edge_key(v, w, 2),
            ]
    return _sphere_board3d("sphere", cells, positions, mine_count)


def _geodesic(frequency: int) -> tuple[dict, list[tuple]]:
    """A geodesic icosahedron: every face subdivided into ``frequency**2``
    triangles, all vertices projected onto the unit sphere.

    Returns (positions, triangles). Vertex keys are gcd-normalized
    barycentric weights over the icosahedron corners, so vertices on
    shared edges match exactly across faces.
    """
    vertices, faces = _icosahedron()
    positions: dict[Hashable, Vec3] = {}
    triangles: list[tuple] = []
    for face in faces:
        corners = [vertices[v] for v in face]

        def key(i: int, j: int):
            weights = (frequency - i - j, i, j)
            items = [(v, w) for v, w in zip(face, weights) if w > 0]
            g = math.gcd(*(w for _, w in items))
            vertex_key = tuple(sorted((v, w // g) for v, w in items))
            if vertex_key not in positions:
                positions[vertex_key] = _normalize(
                    tuple(
                        sum(w * c[axis] for w, c in zip(weights, corners))
                        for axis in range(3)
                    )
                )
            return vertex_key

        for i in range(frequency):
            for j in range(frequency - i):
                triangles.append((key(i, j), key(i + 1, j), key(i, j + 1)))
                if i + j < frequency - 1:
                    triangles.append((key(i + 1, j), key(i + 1, j + 1), key(i, j + 1)))
    return positions, triangles


def _goldberg_board(mode: str, frequency: int, mine_count: int) -> Board3D:
    """The dual of a geodesic icosahedron: one cell per geodesic vertex,
    made of the surrounding triangle centers. Always 12 pentagons plus
    ``10 * frequency**2 - 10`` hexagons."""
    positions, triangles = _geodesic(frequency)
    centers: dict[tuple, Vec3] = {}
    around: dict[Hashable, list[tuple]] = defaultdict(list)
    for triangle in triangles:
        triangle_id = tuple(sorted(triangle))
        centers[triangle_id] = _normalize(
            tuple(
                sum(positions[k][axis] for k in triangle) / 3 for axis in range(3)
            )
        )
        for key in triangle:
            around[key].append(triangle_id)

    cells: dict[Cell, list] = {}
    for key, triangle_ids in around.items():
        ring = [(tid, centers[tid]) for tid in triangle_ids]
        cells[key] = _tangent_order(positions[key], ring)
    return _sphere_board3d(mode, cells, centers, mine_count)


def c80_board(mine_count: int) -> Board3D:
    """A C80 fullerene (chamfered dodecahedron): 12 pentagons and 30
    hexagons, projected onto the unit sphere."""
    return _goldberg_board("c80", 2, mine_count)


def c180_board(mine_count: int) -> Board3D:
    """A C180 fullerene (Goldberg GP(3,0)): 12 pentagons and 80
    hexagons, projected onto the unit sphere."""
    return _goldberg_board("c180", 3, mine_count)


def sphere_triangle_board(mine_count: int, frequency: int = 2) -> Board3D:
    """A sphere tiled with triangles: a geodesic icosahedron with
    ``20 * frequency**2`` triangular cells."""
    positions, triangles = _geodesic(frequency)
    cells = {("t", n): list(triangle) for n, triangle in enumerate(triangles)}
    return _sphere_board3d("spheretri", cells, positions, mine_count)


def _torus_position(i: float, j: float, ring: int, tube: int, tube_radius: float) -> Vec3:
    theta = 2 * math.pi * i / ring
    phi = 2 * math.pi * j / tube
    radial = 1.0 + tube_radius * math.cos(phi)
    return (
        radial * math.cos(theta),
        radial * math.sin(theta),
        tube_radius * math.sin(phi),
    )


def torus_board(
    ring: int, tube: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled with ``ring * tube`` quadrilaterals. The grid wraps
    in both directions, so every cell has exactly 8 neighbors."""
    positions = {
        (i, j): _torus_position(i, j, ring, tube, tube_radius)
        for i in range(ring)
        for j in range(tube)
    }
    cells = {
        (i, j): [
            (i, j),
            ((i + 1) % ring, j),
            ((i + 1) % ring, (j + 1) % tube),
            (i, (j + 1) % tube),
        ]
        for i in range(ring)
        for j in range(tube)
    }
    return _torus_oriented(
        "torus", positions, cells, mine_count, radius=1.0 + tube_radius
    )


def _torus_oriented(mode, positions, cells, mine_count, radius) -> Board3D:
    """Assemble a torus board, orienting each polygon outward (away from
    the ring circle through the tube center)."""
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        ring_scale = math.hypot(centroid[0], centroid[1])
        ring_point = (centroid[0] / ring_scale, centroid[1] / ring_scale, 0.0)
        outward = tuple(c - p for c, p in zip(centroid, ring_point))
        polygons[cell] = _orient_outward(polygon, outward)
    return Board3D(mode, polygons, adjacency, mine_count, radius=radius)


def torus_triangle_board(
    ring: int, tube: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled with triangles: each quad of the torus grid is
    split along a diagonal, giving ``2 * ring * tube`` cells."""
    positions = {
        (i, j): _torus_position(i, j, ring, tube, tube_radius)
        for i in range(ring)
        for j in range(tube)
    }
    cells = {}
    for i in range(ring):
        for j in range(tube):
            a = (i, j)
            b = ((i + 1) % ring, j)
            c = ((i + 1) % ring, (j + 1) % tube)
            d = (i, (j + 1) % tube)
            cells[(i, j, 0)] = [a, b, c]
            cells[(i, j, 1)] = [a, c, d]
    return _torus_oriented(
        "torustri", positions, cells, mine_count, radius=1.0 + tube_radius
    )


def torus_hex_board(
    rows: int, cols: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled entirely with hexagons (possible because the torus
    has Euler characteristic 0). The hex lattice wraps around the tube
    (``rows``, must be even) and around the ring (``cols``); every cell
    has exactly 6 neighbors."""
    if rows % 2:
        raise ValueError("rows must be even so the offset lattice wraps")
    kx_period, ky_period = 2 * cols, 3 * rows

    def position(kx: int, ky: int) -> Vec3:
        theta = 2 * math.pi * kx / kx_period  # around the ring
        phi = 2 * math.pi * ky / ky_period  # around the tube
        radial = 1.0 + tube_radius * math.cos(phi)
        return (
            radial * math.cos(theta),
            radial * math.sin(theta),
            tube_radius * math.sin(phi),
        )

    cells = {}
    positions = {}
    for r in range(rows):
        for c in range(cols):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            keys = [
                ((kx + ox) % kx_period, (ky + oy) % ky_period)
                for ox, oy in _HEX_VERTEX_OFFSETS
            ]
            cells[(r, c)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    return _torus_oriented(
        "torushex", positions, cells, mine_count, radius=1.0 + tube_radius
    )


def mobius_board(ring: int, width_cells: int, mine_count: int) -> Board3D:
    """A Möbius strip tiled with quadrilaterals: ``ring`` segments
    around, ``width_cells`` across. After a full loop the strip flips,
    so column ``ring`` glues to column 0 upside down."""
    half_width = min(0.7, math.pi * width_cells / ring / 2)

    def vertex_key(i: int, j: int) -> LatticePoint:
        if i >= ring:  # the seam: glue to the start, flipped
            return (i - ring, width_cells - j)
        return (i, j)

    def position(i: int, j: int) -> Vec3:
        u = 2 * math.pi * i / ring
        v = half_width * (2 * j / width_cells - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (
            radial * math.cos(u),
            radial * math.sin(u),
            v * math.sin(u / 2),
        )

    positions = {
        (i, j): position(i, j)
        for i in range(ring)
        for j in range(width_cells + 1)
    }
    cells = {
        (i, j): [
            vertex_key(i, j),
            vertex_key(i + 1, j),
            vertex_key(i + 1, j + 1),
            vertex_key(i, j + 1),
        ]
        for i in range(ring)
        for j in range(width_cells)
    }
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "mobius",
        polygons,
        adjacency,
        mine_count,
        radius=1.0 + half_width,
        two_sided=True,  # non-orientable: no consistent outside
    )


def mobius_triangle_board(ring: int, width_cells: int, mine_count: int) -> Board3D:
    """A Möbius strip tiled with triangles: each quad of the strip is
    split along a diagonal, giving ``2 * ring * width_cells`` cells."""
    half_width = min(0.7, math.pi * width_cells / ring / 2)

    def vertex_key(i: int, j: int):
        if i >= ring:
            return (i - ring, width_cells - j)
        return (i, j)

    def position(i: int, j: int) -> Vec3:
        u = 2 * math.pi * i / ring
        v = half_width * (2 * j / width_cells - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (radial * math.cos(u), radial * math.sin(u), v * math.sin(u / 2))

    positions = {
        (i, j): position(i, j)
        for i in range(ring)
        for j in range(width_cells + 1)
    }
    cells = {}
    for i in range(ring):
        for j in range(width_cells):
            a = vertex_key(i, j)
            b = vertex_key(i + 1, j)
            c = vertex_key(i + 1, j + 1)
            d = vertex_key(i, j + 1)
            cells[(i, j, 0)] = [a, b, c]
            cells[(i, j, 1)] = [a, c, d]
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "mobiustri", polygons, adjacency, mine_count,
        radius=1.0 + half_width, two_sided=True,
    )


def mobius_hex_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """A Möbius strip tiled with hexagons: ``ring`` columns of ``rows``
    hexagons glued end-to-start with a vertical flip. ``rows`` must be
    odd so the offset lattice maps onto itself under the flip."""
    if rows % 2 == 0:
        raise ValueError("rows must be odd so the lattice survives the flip")
    kx_period = 2 * ring
    ky_top = 3 * rows + 1  # the flip mirrors ky about the strip center
    half_width = min(0.7, math.pi * rows / ring)

    def canonical(kx: int, ky: int):
        if kx >= kx_period:
            return (kx - kx_period, ky_top - ky)
        return (kx, ky)

    def position(kx: int, ky: int) -> Vec3:
        u = 2 * math.pi * kx / kx_period
        v = half_width * (2 * ky / ky_top - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (radial * math.cos(u), radial * math.sin(u), v * math.sin(u / 2))

    cells = {}
    positions = {}
    for c in range(ring):
        for r in range(rows):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            keys = [canonical(kx + ox, ky + oy) for ox, oy in _HEX_VERTEX_OFFSETS]
            cells[(r, c)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "mobiushex", polygons, adjacency, mine_count,
        radius=1.0 + half_width, two_sided=True,
    )


def cylinder_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """The side surface of a cylinder tiled with quadrilaterals: ``ring``
    segments around, ``rows`` up the axis. Wraps around the ring only;
    the ends are open, so the inside is visible."""
    row_height = 2 * math.pi / ring * 0.9  # near-square tiles
    height = rows * row_height

    def position(i: int, j: int) -> Vec3:
        theta = 2 * math.pi * i / ring
        return (math.cos(theta), j * row_height - height / 2, math.sin(theta))

    positions = {
        (i, j): position(i, j) for i in range(ring) for j in range(rows + 1)
    }
    cells = {
        (i, j): [
            (i, j),
            ((i + 1) % ring, j),
            ((i + 1) % ring, j + 1),
            (i, j + 1),
        ]
        for i in range(ring)
        for j in range(rows)
    }
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "cylinder",
        polygons,
        adjacency,
        mine_count,
        radius=math.hypot(1.0, height / 2),
        two_sided=True,  # open ends: the inner surface is visible
    )


def cylinder_triangle_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """The side of a cylinder tiled with triangles: ``ring`` triangles
    around (must be even so up/down triangles alternate cleanly across
    the seam), ``rows`` up the axis."""
    if ring % 2:
        raise ValueError("ring must be even for the triangle strip to wrap")
    # lattice x unit is half a triangle side; make triangles near-equilateral
    row_height = 2 * math.pi / ring * ROOT3 * 0.9
    height = rows * row_height

    def position(kx: int, ky: int) -> Vec3:
        theta = 2 * math.pi * kx / ring
        return (math.cos(theta), ky * row_height - height / 2, math.sin(theta))

    cells = {}
    positions = {}
    for r in range(rows):
        for i in range(ring):
            keys = [
                (kx % ring, ky)
                for kx, ky in _triangle_vertices(i, r, up=(r + i) % 2 == 0)
            ]
            cells[(r, i)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "cyltri", polygons, adjacency, mine_count,
        radius=math.hypot(1.0, height / 2), two_sided=True,
    )


def cylinder_hex_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """The side of a cylinder tiled with hexagons: ``ring`` columns
    around, ``rows`` up the axis."""
    kx_period = 2 * ring
    # lattice units for regular hexagons: x = sqrt(3)/2 * s, y = s / 2,
    # with the x unit pinned to the arc length around the cylinder
    ky_unit = 2 * math.pi / kx_period / ROOT3
    height = (3 * rows + 1) * ky_unit

    def position(kx: int, ky: int) -> Vec3:
        theta = 2 * math.pi * kx / kx_period
        return (math.cos(theta), ky * ky_unit - height / 2, math.sin(theta))

    cells = {}
    positions = {}
    for r in range(rows):
        for c in range(ring):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            keys = [
                ((kx + ox) % kx_period, ky + oy) for ox, oy in _HEX_VERTEX_OFFSETS
            ]
            cells[(r, c)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "cylhex", polygons, adjacency, mine_count,
        radius=math.hypot(1.0, height / 2), two_sided=True,
    )


# -- presets ---------------------------------------------------------------

_PRESETS = {
    "square": {
        "easy": lambda: square_board(9, 9, 10, scale=32),
        "medium": lambda: square_board(16, 16, 40, scale=32),
        "hard": lambda: square_board(16, 30, 99, scale=32),
    },
    "triangle": {
        "easy": lambda: triangle_board(8, 10, scale=60),
        "medium": lambda: triangle_board(12, 24, scale=52),
        "hard": lambda: triangle_board(16, 48, scale=44),
    },
    "trigrid": {
        "easy": lambda: triangle_grid_board(7, 11, 11, scale=52),
        "medium": lambda: triangle_grid_board(10, 16, 26, scale=44),
        "hard": lambda: triangle_grid_board(14, 23, 62, scale=36),
    },
    "hex": {
        "easy": lambda: hex_board(11, 9, 12, scale=24),
        "medium": lambda: hex_board(15, 13, 30, scale=20),
        "hard": lambda: hex_board(20, 17, 68, scale=17),
    },
    "hexhex": {
        "easy": lambda: hexhex_board(5, 12, scale=25),
        "medium": lambda: hexhex_board(7, 28, scale=21),
        "hard": lambda: hexhex_board(9, 58, scale=18),
    },
    "penrose": {
        "easy": lambda: penrose_board(3, 9, scale=220),
        "medium": lambda: penrose_board(4, 25, scale=280),
        "hard": lambda: penrose_board(5, 70, scale=340),
    },
    "sphere": {
        "easy": lambda: sphere_board(7),
        "medium": lambda: sphere_board(10),
        "hard": lambda: sphere_board(14),
    },
    "c80": {
        "easy": lambda: c80_board(5),
        "medium": lambda: c80_board(8),
        "hard": lambda: c80_board(11),
    },
    "c180": {
        "easy": lambda: c180_board(10),
        "medium": lambda: c180_board(14),
        "hard": lambda: c180_board(19),
    },
    "spheretri": {
        "easy": lambda: sphere_triangle_board(10),
        "medium": lambda: sphere_triangle_board(14),
        "hard": lambda: sphere_triangle_board(18),
    },
    "torus": {
        "easy": lambda: torus_board(12, 6, 9),
        "medium": lambda: torus_board(16, 8, 20),
        "hard": lambda: torus_board(24, 10, 48),
    },
    "torustri": {
        "easy": lambda: torus_triangle_board(10, 5, 12),
        "medium": lambda: torus_triangle_board(14, 7, 30),
        "hard": lambda: torus_triangle_board(18, 9, 60),
    },
    "torushex": {
        "easy": lambda: torus_hex_board(6, 12, 9),
        "medium": lambda: torus_hex_board(8, 16, 20),
        "hard": lambda: torus_hex_board(10, 24, 44),
    },
    "mobius": {
        "easy": lambda: mobius_board(20, 4, 10),
        "medium": lambda: mobius_board(28, 5, 22),
        "hard": lambda: mobius_board(36, 6, 40),
    },
    "mobiustri": {
        "easy": lambda: mobius_triangle_board(14, 4, 13),
        "medium": lambda: mobius_triangle_board(20, 5, 30),
        "hard": lambda: mobius_triangle_board(28, 6, 62),
    },
    "mobiushex": {
        "easy": lambda: mobius_hex_board(14, 3, 6),
        "medium": lambda: mobius_hex_board(20, 5, 16),
        "hard": lambda: mobius_hex_board(26, 7, 34),
    },
    "cylinder": {
        "easy": lambda: cylinder_board(12, 7, 10),
        "medium": lambda: cylinder_board(16, 10, 26),
        "hard": lambda: cylinder_board(22, 13, 60),
    },
    "cyltri": {
        "easy": lambda: cylinder_triangle_board(16, 6, 11),
        "medium": lambda: cylinder_triangle_board(22, 9, 32),
        "hard": lambda: cylinder_triangle_board(28, 12, 64),
    },
    "cylhex": {
        "easy": lambda: cylinder_hex_board(12, 6, 9),
        "medium": lambda: cylinder_hex_board(16, 9, 24),
        "hard": lambda: cylinder_hex_board(20, 12, 46),
    },
}


def build_board(mode: str, difficulty: str) -> Board | Board3D:
    if mode not in _PRESETS:
        raise ValueError(f"unknown mode {mode!r}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    return _PRESETS[mode][difficulty]()
