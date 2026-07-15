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


_HEX_VERTEX_OFFSETS = [(0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1)]


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
