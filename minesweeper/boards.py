"""Board geometry: tilings of squares, triangles and hexagons.

Every board is a set of congruent polygonal cells. Cell vertices are
generated on an integer lattice (scaled to pixels afterwards), so cells
that touch can be matched exactly: two cells are neighbors when they
share at least one lattice vertex. That rule yields the classic
8-neighborhood for squares, 6 for hexagons and 12 for triangles.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable

Cell = Hashable
LatticePoint = tuple[int, int]

ROOT3 = 3**0.5

DIFFICULTIES = ("easy", "medium", "hard")

MODE_LABELS = {
    "square": "Classic squares",
    "triangle": "Triangle of triangles",
    "trigrid": "Triangle grid",
    "hex": "Hexagon grid",
}


@dataclass(frozen=True)
class Board:
    mode: str
    polygons: dict[Cell, list[tuple[float, float]]]  # pixel-space vertices
    adjacency: dict[Cell, tuple[Cell, ...]]
    mine_count: int
    width: float
    height: float


def _build(
    mode: str,
    lattice_cells: dict[Cell, list[LatticePoint]],
    unit: tuple[float, float],
    mine_count: int,
) -> Board:
    if not lattice_cells:
        raise ValueError("board has no cells")
    by_vertex: dict[LatticePoint, list[Cell]] = defaultdict(list)
    for cell, vertices in lattice_cells.items():
        for vertex in vertices:
            by_vertex[vertex].append(cell)
    touching: dict[Cell, set[Cell]] = {cell: set() for cell in lattice_cells}
    for group in by_vertex.values():
        for cell in group:
            touching[cell].update(group)
    adjacency = {
        cell: tuple(sorted(others - {cell})) for cell, others in touching.items()
    }

    ux, uy = unit
    polygons = {
        cell: [(kx * ux, ky * uy) for kx, ky in vertices]
        for cell, vertices in lattice_cells.items()
    }
    width = max(x for polygon in polygons.values() for x, _ in polygon)
    height = max(y for polygon in polygons.values() for _, y in polygon)
    return Board(mode, polygons, adjacency, mine_count, width, height)


# -- builders (cells keyed by (row, index)) -------------------------------


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
    """A parallelogram-ish strip surface: ``rows`` rows of ``row_width``
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


# -- presets ---------------------------------------------------------------

_PRESETS = {
    "square": {
        "easy": (square_board, (9, 9, 10), 32),
        "medium": (square_board, (16, 16, 40), 32),
        "hard": (square_board, (16, 30, 99), 32),
    },
    "triangle": {
        "easy": (triangle_board, (8, 10), 60),
        "medium": (triangle_board, (12, 24), 52),
        "hard": (triangle_board, (16, 48), 44),
    },
    "trigrid": {
        "easy": (triangle_grid_board, (6, 13, 11), 60),
        "medium": (triangle_grid_board, (9, 21, 32), 50),
        "hard": (triangle_grid_board, (12, 29, 68), 44),
    },
    "hex": {
        "easy": (hex_board, (9, 9, 10), 24),
        "medium": (hex_board, (14, 14, 30), 21),
        "hard": (hex_board, (16, 24, 75), 19),
    },
}


def build_board(mode: str, difficulty: str) -> Board:
    if mode not in _PRESETS:
        raise ValueError(f"unknown mode {mode!r}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    builder, args, scale = _PRESETS[mode][difficulty]
    return builder(*args, scale=scale)
