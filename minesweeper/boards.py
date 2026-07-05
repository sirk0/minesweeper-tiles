"""Board geometry: tilings of squares, triangles, hexagons — and 3D
surfaces (a pentagon-tiled sphere and a quad-tiled torus).

Every board is a set of polygonal cells. Cell vertices are generated
with exact, hashable ids (integer lattice points in 2D, symbolic keys
in 3D), so cells that touch can be matched exactly: two cells are
neighbors when they share at least one vertex. That rule yields the
classic 8-neighborhood for squares, 6 for hexagons, 12 for triangles,
8 for torus quads and 7 for the sphere pentagons.
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
    "square": "Classic squares",
    "triangle": "Triangle of triangles",
    "trigrid": "Triangle grid",
    "hex": "Hexagon grid",
    "sphere": "Pentagon sphere (3D)",
    "torus": "Square donut (3D)",
}

MODES_3D = frozenset({"sphere", "torus"})


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


def hex_board(rows: int, cols: int, mine_count: int, scale: float = 20) -> Board:
    """Pointy-top hexagons in odd-r offset layout; ``scale`` is the hexagon
    circumradius. Lattice units: x = sqrt(3)/2 * scale, y = scale / 2."""
    offsets = [(0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1)]
    cells = {}
    for r in range(rows):
        for c in range(cols):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            cells[(r, c)] = [(kx + ox, ky + oy) for ox, oy in offsets]
    return _build("hex", cells, (scale * ROOT3 / 2, scale / 2), mine_count)


# -- 3D helpers --------------------------------------------------------------


def _normalize(v: Vec3) -> Vec3:
    length = math.hypot(*v)
    return (v[0] / length, v[1] / length, v[2] / length)


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
    dot = sum(n * o for n, o in zip(normal, outward))
    return polygon if dot > 0 else list(reversed(polygon))


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
                    # gyro needs consistent winding: orient every face
                    # counterclockwise as seen from outside
                    a, b, c = (vertices[n] for n in (i, j, k))
                    normal = newell_normal([a, b, c])
                    outward = sum(n * (pa + pb + pc) for n, pa, pb, pc in zip(normal, a, b, c))
                    faces.append((i, j, k) if outward > 0 else (i, k, j))
    assert len(faces) == 20
    return vertices, faces


# -- 3D builders --------------------------------------------------------------


def sphere_board(mine_count: int) -> Board3D:
    """A sphere tiled with 60 pentagons (a pentagonal hexecontahedron,
    projected onto the unit sphere).

    Built with the Conway "gyro" operation on an icosahedron: each
    triangular face gains a center vertex, each edge two division
    points, and every (face, corner) pair becomes one pentagon. Vertex
    ids are symbolic, so shared-vertex adjacency is exact: every
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

    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        polygons[cell] = _orient_outward(polygon, centroid)
    return Board3D("sphere", polygons, adjacency, mine_count, radius=1.0)


def torus_board(
    ring: int, tube: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled with ``ring * tube`` quadrilaterals. The grid wraps
    in both directions, so every cell has exactly 8 neighbors."""
    def position(i: int, j: int) -> Vec3:
        theta = 2 * math.pi * i / ring
        phi = 2 * math.pi * j / tube
        radial = 1.0 + tube_radius * math.cos(phi)
        return (
            radial * math.cos(theta),
            radial * math.sin(theta),
            tube_radius * math.sin(phi),
        )

    positions = {
        (i, j): position(i, j) for i in range(ring) for j in range(tube)
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
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        # outward = away from the ring circle through the tube center
        ring_scale = math.hypot(centroid[0], centroid[1])
        ring_point = (centroid[0] / ring_scale, centroid[1] / ring_scale, 0.0)
        outward = tuple(c - p for c, p in zip(centroid, ring_point))
        polygons[cell] = _orient_outward(polygon, outward)
    return Board3D(
        "torus", polygons, adjacency, mine_count, radius=1.0 + tube_radius
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
        "easy": lambda: triangle_grid_board(6, 13, 11, scale=60),
        "medium": lambda: triangle_grid_board(9, 21, 32, scale=50),
        "hard": lambda: triangle_grid_board(12, 29, 68, scale=44),
    },
    "hex": {
        "easy": lambda: hex_board(9, 9, 10, scale=24),
        "medium": lambda: hex_board(14, 14, 30, scale=21),
        "hard": lambda: hex_board(16, 24, 75, scale=19),
    },
    "sphere": {
        "easy": lambda: sphere_board(7),
        "medium": lambda: sphere_board(10),
        "hard": lambda: sphere_board(14),
    },
    "torus": {
        "easy": lambda: torus_board(12, 6, 9),
        "medium": lambda: torus_board(16, 8, 20),
        "hard": lambda: torus_board(24, 10, 48),
    },
}


def build_board(mode: str, difficulty: str) -> Board | Board3D:
    if mode not in _PRESETS:
        raise ValueError(f"unknown mode {mode!r}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    return _PRESETS[mode][difficulty]()
