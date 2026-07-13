"""Board geometry: flat tilings (squares, triangles, hexagons) and 3D
surfaces (spheres, fullerenes, a cube, a tetrahedron, a donut, a Möbius
strip, a cylinder).

Every board is a set of polygonal cells. Cell vertices are generated
with exact, hashable ids (integer lattice points in 2D, symbolic keys
in 3D), so cells that touch can be matched exactly: two cells are
neighbors when they share at least one vertex.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
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
    "hat": "The Hat",
    "elongated": "Elongated triangular",
    "snubsquare": "Snub square",
    "kagome": "Kagome",
    "snubhex": "Snub hexagonal",
    "truncsquare": "Truncated square",
    "trunchex": "Truncated hexagonal",
    "sphere": "60 pentagons",
    "c80": "C80 fullerene",
    "c180": "C180 fullerene",
    "spheretri": "Triangles",
    "snubdodec": "Snub dodecahedron",
    "cube": "Cube",
    "tetrahedron": "Tetrahedron",
    "tetraframe": "Tetrahedron frame",
    "cubeframe": "Cube frame",
    "steppedbipyramid": "Stepped bipyramid",
    "torus": "Squares",
    "torustri": "Triangles",
    "torushex": "Hexagons",
    "toruselongated": "Elongated triangular",
    "torussnubsquare": "Snub square",
    "toruskagome": "Kagome",
    "torussnubhex": "Snub hexagonal",
    "torustruncsquare": "Truncated square",
    "torustrunchex": "Truncated hexagonal",
    "mobius": "Squares",
    "mobiustri": "Triangles",
    "mobiushex": "Hexagons",
    "mobiuselongated": "Elongated triangular",
    "mobiussnubsquare": "Snub square",
    "mobiuskagome": "Kagome",
    "mobiustruncsquare": "Truncated square",
    "mobiustrunchex": "Truncated hexagonal",
    "cylinder": "Squares",
    "cyltri": "Triangles",
    "cylhex": "Hexagons",
    "cylelongated": "Elongated triangular",
    "cylsnubsquare": "Snub square",
    "cylkagome": "Kagome",
    "cylsnubhex": "Snub hexagonal",
    "cyltruncsquare": "Truncated square",
    "cyltrunchex": "Truncated hexagonal",
}

# The menu picks a group, then a tiling, then — for the periodic
# tilings — a surface. Every periodic tiling wraps every surface, with
# one exception: 3.3.3.3.6 (snub hexagonal) is chiral (p6, no mirror or
# glide), so the orientation-reversing Möbius seam cannot glue it to
# itself; the menu shows that surface disabled. The sphere is its own
# group: none of these periodic patterns can tile it (Euler's formula
# forces curvature in), so it offers spherical tilings instead.

SURFACE_LABELS = {
    "flat": "Flat",
    "torus": "Donut",
    "cylinder": "Cylinder",
    "mobius": "Möbius strip",
}

TILINGS = {  # tiling -> (label, {surface: mode})
    "square": (
        "Squares",
        {"flat": "square", "torus": "torus",
         "cylinder": "cylinder", "mobius": "mobius"},
    ),
    "tri": (
        "Triangles",
        {"flat": "trigrid", "torus": "torustri",
         "cylinder": "cyltri", "mobius": "mobiustri"},
    ),
    "hex": (
        "Hexagons",
        {"flat": "hex", "torus": "torushex",
         "cylinder": "cylhex", "mobius": "mobiushex"},
    ),
    "elongated": (
        "Elongated triangular",
        {"flat": "elongated", "torus": "toruselongated",
         "cylinder": "cylelongated", "mobius": "mobiuselongated"},
    ),
    "snubsquare": (
        "Snub square",
        {"flat": "snubsquare", "torus": "torussnubsquare",
         "cylinder": "cylsnubsquare", "mobius": "mobiussnubsquare"},
    ),
    "kagome": (
        "Kagome",
        {"flat": "kagome", "torus": "toruskagome",
         "cylinder": "cylkagome", "mobius": "mobiuskagome"},
    ),
    "snubhex": (
        "Snub hexagonal",
        {"flat": "snubhex", "torus": "torussnubhex",
         "cylinder": "cylsnubhex"},  # chiral: no Möbius strip
    ),
    "truncsquare": (
        "Truncated square",
        {"flat": "truncsquare", "torus": "torustruncsquare",
         "cylinder": "cyltruncsquare", "mobius": "mobiustruncsquare"},
    ),
    "trunchex": (
        "Truncated hexagonal",
        {"flat": "trunchex", "torus": "torustrunchex",
         "cylinder": "cyltrunchex", "mobius": "mobiustrunchex"},
    ),
}

GROUPS = {  # group -> (label, modes); the periodic group goes via TILINGS
    "periodic": ("Periodic tilings", ()),
    "aperiodic": ("Aperiodic", ("penrose", "hat")),
    "sphere": ("Sphere", ("sphere", "c80", "c180", "spheretri", "snubdodec")),
    "polyhedra": (
        "Polyhedra",
        ("cube", "tetrahedron", "tetraframe", "cubeframe", "steppedbipyramid"),
    ),
    "shaped": ("Shaped boards", ("triangle", "hexhex")),
}

MODES_3D = frozenset(
    {"sphere", "c80", "c180", "spheretri", "snubdodec", "cube", "tetrahedron",
     "tetraframe", "cubeframe", "steppedbipyramid"}
    | {mode for mode in MODE_LABELS if mode.startswith(("torus", "mobius", "cyl"))}
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


def penrose_board(
    subdivisions: int, mine_count: int, scale: float = 300, keep: int | None = None
) -> Board:
    """An aperiodic Penrose tiling (P3): thick and thin rhombi.

    Starts from a wheel of ten half-rhombus Robinson triangles and
    deflates ``subdivisions`` times; mirror-image triangle halves are
    then merged into rhombi (unpaired halves on the outer rim are
    dropped). ``scale`` is the wheel radius in pixels. ``keep`` trims the
    tiling to its ``keep`` centremost rhombi by Chebyshev distance (a
    roughly square block, denser on screen than the full round wheel);
    ``None`` keeps the whole decagonal patch.
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

    if keep is not None and keep < len(cells):
        centroid = {
            cell: (sum(_z_to_xy(k)[0] for k in quad) / 4,
                   sum(_z_to_xy(k)[1] for k in quad) / 4)
            for cell, quad in cells.items()
        }
        gx = sum(c[0] for c in centroid.values()) / len(centroid)
        gy = sum(c[1] for c in centroid.values()) / len(centroid)
        kept = sorted(cells, key=lambda cell: (
            max(abs(centroid[cell][0] - gx), abs(centroid[cell][1] - gy)), cell))
        cells = {cell: cells[cell] for cell in kept[:keep]}

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


# -- The Hat: an aperiodic monotile ------------------------------------------
#
# "The Hat" (Smith-Myers-Kaplan-Goodman-Strauss, 2023) is a single
# 13-sided tile that tiles the plane only aperiodically. Every hat
# vertex lies on the Eisenstein integer lattice -- point (a, b) is
# a*(1,0) + b*(1/2, sqrt3/2) = _hexpt(a, b) -- so a vertex id is an
# exact integer pair and shared-vertex adjacency needs no tolerance,
# just like penrose_board above.
#
# The tiling is grown by the H/T/P/F metatile substitution. The
# substitution transforms are ported from Craig S. Kaplan's "hatviz"
# reference (github.com/isohedral/hatviz, BSD 3-Clause, (c) 2023 Craig
# S. Kaplan). Those transforms carry irrational (sqrt3) translations, so
# they run in floating point; each final vertex is then snapped back to
# its exact Eisenstein integer id. The lattice spacing is 1 and the
# accumulated error over a handful of inflations is ~1e-13, so the snap
# is exact and two hats meeting at a point snap to the same id -- float
# is transient, ids are exact, seams are impossible.

_HR3 = ROOT3 / 2
_AFF_IDENT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)  # 2x3 affine: x'=ax+by+c, y'=dx+ey+f


def _aff_mul(A, B):
    return (A[0]*B[0] + A[1]*B[3], A[0]*B[1] + A[1]*B[4], A[0]*B[2] + A[1]*B[5] + A[2],
            A[3]*B[0] + A[4]*B[3], A[3]*B[1] + A[4]*B[4], A[3]*B[2] + A[4]*B[5] + A[5])


def _aff_inv(T):
    det = T[0]*T[4] - T[1]*T[3]
    return (T[4]/det, -T[1]/det, (T[1]*T[5]-T[2]*T[4])/det,
            -T[3]/det, T[0]/det, (T[2]*T[3]-T[0]*T[5])/det)


def _aff_pt(M, p):
    return (M[0]*p[0] + M[1]*p[1] + M[2], M[3]*p[0] + M[4]*p[1] + M[5])


def _trot(ang):
    c, s = math.cos(ang), math.sin(ang)
    return (c, -s, 0.0, s, c, 0.0)


def _ttrans(tx, ty):
    return (1.0, 0.0, tx, 0.0, 1.0, ty)


def _rot_about(p, ang):
    return _aff_mul(_ttrans(p[0], p[1]), _aff_mul(_trot(ang), _ttrans(-p[0], -p[1])))


def _match_seg(p, q):
    return (q[0]-p[0], p[1]-q[1], p[0], q[1]-p[1], q[0]-p[0], p[1])


def _match_two(p1, q1, p2, q2):
    return _aff_mul(_match_seg(p2, q2), _aff_inv(_match_seg(p1, q1)))


def _line_intersect(p1, q1, p2, q2):
    d = (q2[1]-p2[1])*(q1[0]-p1[0]) - (q2[0]-p2[0])*(q1[1]-p1[1])
    u = ((q2[0]-p2[0])*(p1[1]-p2[1]) - (q2[1]-p2[1])*(p1[0]-p2[0])) / d
    return (p1[0] + u*(q1[0]-p1[0]), p1[1] + u*(q1[1]-p1[1]))


def _hexpt(a, b):
    return (a + 0.5*b, _HR3*b)


# The hat as its 13 corners (Kaplan's hat_outline) -- a true tridecagon.
# All 13 are exact lattice points, and every edge but one is a single
# lattice step; the lone non-primitive edge (0,-2)->(2,-2) passes through
# (1,-2), but no neighbouring hat ever plants a corner there (verified
# over a full patch), so the 13 corners capture every shared vertex and
# no T-junction is missed. These points seed both the metatile placement
# and the per-hat vertex ids.
_HAT_OUTLINE = [
    _hexpt(0, 0), _hexpt(-1, -1), _hexpt(0, -2), _hexpt(2, -2), _hexpt(2, -1),
    _hexpt(4, -2), _hexpt(5, -1), _hexpt(4, 0), _hexpt(3, 0), _hexpt(2, 2),
    _hexpt(0, 3), _hexpt(0, 2), _hexpt(-1, 2)]


class _HatTile:
    __slots__ = ("label",)

    def __init__(self, label):
        self.label = label


class _MetaTile:
    __slots__ = ("shape", "width", "children")

    def __init__(self, shape, width):
        self.shape = list(shape)
        self.width = width
        self.children = []  # list of (transform, geom)

    def add_child(self, T, geom):
        self.children.append((T, geom))

    def eval_child(self, n, i):
        T, geom = self.children[n]
        return _aff_pt(T, geom.shape[i])

    def recentre(self):
        cx = sum(p[0] for p in self.shape) / len(self.shape)
        cy = sum(p[1] for p in self.shape) / len(self.shape)
        self.shape = [(x - cx, y - cy) for x, y in self.shape]
        M = _ttrans(-cx, -cy)
        self.children = [(_aff_mul(M, T), geom) for T, geom in self.children]


# The four metatile substitution rules (verbatim from hatviz). Each rule
# places one child relative to already-placed children; see _construct_patch.
_HAT_RULES = [
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
]


def _hat_base_tiles():
    """The four level-0 metatiles H, T, P, F, each a cluster of hats."""
    H1, H, T, P, F = (_HatTile(s) for s in ("H1", "H", "T", "P", "F"))
    o = _HAT_OUTLINE

    H_out = [(0, 0), (4, 0), (4.5, _HR3), (2.5, 5*_HR3), (1.5, 5*_HR3), (-0.5, _HR3)]
    hm = _MetaTile(H_out, 2)
    hm.add_child(_match_two(o[5], o[7], H_out[5], H_out[0]), H)
    hm.add_child(_match_two(o[9], o[11], H_out[1], H_out[2]), H)
    hm.add_child(_match_two(o[5], o[7], H_out[3], H_out[4]), H)
    hm.add_child(_aff_mul(_ttrans(2.5, _HR3),
                          _aff_mul((-0.5, -_HR3, 0, _HR3, -0.5, 0),
                                   (0.5, 0, 0, 0, -0.5, 0))), H1)

    tm = _MetaTile([(0, 0), (3, 0), (1.5, 3*_HR3)], 2)
    tm.add_child((0.5, 0, 0.5, 0, 0.5, _HR3), T)

    pm = _MetaTile([(0, 0), (4, 0), (3, 2*_HR3), (-1, 2*_HR3)], 2)
    pm.add_child((0.5, 0, 1.5, 0, 0.5, _HR3), P)
    pm.add_child(_aff_mul(_ttrans(0, 2*_HR3),
                          _aff_mul((0.5, _HR3, 0, -_HR3, 0.5, 0),
                                   (0.5, 0, 0, 0, 0.5, 0))), P)

    fm = _MetaTile([(0, 0), (3, 0), (3.5, _HR3), (3, 2*_HR3), (-1, 2*_HR3)], 2)
    fm.add_child((0.5, 0, 1.5, 0, 0.5, _HR3), F)
    fm.add_child(_aff_mul(_ttrans(0, 2*_HR3),
                          _aff_mul((0.5, _HR3, 0, -_HR3, 0.5, 0),
                                   (0.5, 0, 0, 0, 0.5, 0))), F)

    return [hm, tm, pm, fm]


def _construct_patch(H, T, P, F):
    shapes = {"H": H, "T": T, "P": P, "F": F}
    ret = _MetaTile([], H.width)
    for r in _HAT_RULES:
        if len(r) == 1:
            ret.add_child(_AFF_IDENT, shapes[r[0]])
        elif len(r) == 4:
            Tc, geom = ret.children[r[0]]
            poly = geom.shape
            n = len(poly)
            p = _aff_pt(Tc, poly[(r[1]+1) % n])
            q = _aff_pt(Tc, poly[r[1]])
            npoly = shapes[r[2]].shape
            m = len(npoly)
            ret.add_child(_match_two(npoly[r[3]], npoly[(r[3]+1) % m], p, q),
                          shapes[r[2]])
        else:
            TP, gP = ret.children[r[0]]
            TQ, gQ = ret.children[r[2]]
            p = _aff_pt(TQ, gQ.shape[r[3]])
            q = _aff_pt(TP, gP.shape[r[1]])
            npoly = shapes[r[4]].shape
            m = len(npoly)
            ret.add_child(_match_two(npoly[r[5]], npoly[(r[5]+1) % m], p, q),
                          shapes[r[4]])
    return ret


def _construct_metatiles(patch):
    """Assemble the next-level H, T, P, F supertiles from a patch."""
    bps1 = patch.eval_child(8, 2)
    bps2 = patch.eval_child(21, 2)
    rbps = _aff_pt(_rot_about(bps1, -2.0*math.pi/3.0), bps2)
    p72 = patch.eval_child(7, 2)
    p252 = patch.eval_child(25, 2)

    llc = _line_intersect(bps1, rbps, patch.eval_child(6, 2), p72)
    w = (patch.eval_child(6, 2)[0] - llc[0], patch.eval_child(6, 2)[1] - llc[1])

    nH = [llc, bps1]
    w = _aff_pt(_trot(-math.pi/3), w)
    nH.append((nH[1][0]+w[0], nH[1][1]+w[1]))
    nH.append(patch.eval_child(14, 2))
    w = _aff_pt(_trot(-math.pi/3), w)
    nH.append((nH[3][0]-w[0], nH[3][1]-w[1]))
    nH.append(patch.eval_child(6, 2))
    new_H = _MetaTile(nH, patch.width*2)
    for ch in (0, 9, 16, 27, 26, 6, 1, 8, 10, 15):
        new_H.add_child(*patch.children[ch])

    nP = [p72, (p72[0]+bps1[0]-llc[0], p72[1]+bps1[1]-llc[1]), bps1, llc]
    new_P = _MetaTile(nP, patch.width*2)
    for ch in (7, 2, 3, 4, 28):
        new_P.add_child(*patch.children[ch])

    nF = [bps2, patch.eval_child(24, 2), patch.eval_child(25, 0), p252,
          (p252[0]+llc[0]-bps1[0], p252[1]+llc[1]-bps1[1])]
    new_F = _MetaTile(nF, patch.width*2)
    for ch in (21, 20, 22, 23, 24, 25):
        new_F.add_child(*patch.children[ch])

    AAA = nH[2]
    BBB = (nH[1][0]+nH[4][0]-nH[5][0], nH[1][1]+nH[4][1]-nH[5][1])
    CCC = _aff_pt(_rot_about(BBB, -math.pi/3), AAA)
    new_T = _MetaTile([BBB, CCC, AAA], patch.width*2)
    new_T.add_child(*patch.children[11])

    for m in (new_H, new_P, new_F, new_T):
        m.recentre()
    return [new_H, new_T, new_P, new_F]


def _hat_leaves(geom, M, out):
    if isinstance(geom, _HatTile):
        out.append((geom.label, M))
    else:
        for T, child in geom.children:
            _hat_leaves(child, _aff_mul(M, T), out)


def _hat_snap(p):
    b = round(2 * p[1] / _HR3)
    a = round(2 * p[0] - 0.5 * b)
    return (a, b)


def hat_board(
    levels: int, mine_count: int, keep: int | None = None, scale: float = 14
) -> Board:
    """The Hat aperiodic monotile, grown by ``levels`` of the H/T/P/F
    metatile substitution from a single H seed. ``keep`` trims the patch
    to its ``keep`` centremost hats by Chebyshev distance (a roughly
    square board with an exact cell count); ``None`` keeps the whole
    (ragged, star-shaped) patch.
    """
    tiles = _hat_base_tiles()
    for _ in range(levels):
        tiles = _construct_metatiles(_construct_patch(*tiles))
    hats: list = []
    _hat_leaves(tiles[0], _AFF_IDENT, hats)

    rows = []  # (label, ids, cx, cy)
    seen = set()
    for label, M in hats:
        ids = [_hat_snap(_aff_pt(M, p)) for p in _HAT_OUTLINE]
        fs = frozenset(ids)
        if fs in seen:  # defensive: a single H seed produces no duplicates
            continue
        seen.add(fs)
        cx = sum(_hexpt(*v)[0] for v in ids) / len(ids)
        cy = sum(_hexpt(*v)[1] for v in ids) / len(ids)
        rows.append((label, ids, cx, cy))

    if keep is not None and keep < len(rows):
        # Keep the hats nearest the centre by Chebyshev distance, which
        # trims the patch to a square (packing more tiles per screen than
        # a round Euclidean crop would).
        gx = sum(r[2] for r in rows) / len(rows)
        gy = sum(r[3] for r in rows) / len(rows)
        rows.sort(key=lambda r: (max(abs(r[2]-gx), abs(r[3]-gy)),
                                 tuple(sorted(r[1]))))
        rows = rows[:keep]

    cells: dict[Cell, list] = {
        (label, i): ids for i, (label, ids, _, _) in enumerate(rows)
    }
    adjacency = _shared_vertex_adjacency(cells)
    xy = {v: _hexpt(*v) for ids in cells.values() for v in ids}
    min_x = min(x for x, _ in xy.values())
    min_y = min(y for _, y in xy.values())
    polygons = {
        cell: [((x - min_x) * scale, (y - min_y) * scale)
               for x, y in (xy[v] for v in ids)]
        for cell, ids in cells.items()
    }
    width = max(x for polygon in polygons.values() for x, _ in polygon)
    height = max(y for polygon in polygons.values() for _, y in polygon)
    return Board("hat", polygons, adjacency, mine_count, width, height)


# -- Archimedean (semiregular) tilings ---------------------------------------
#
# The six uniform tilings with two tile shapes are grown outward from a
# seed vertex, placing one polygon at a time wherever the vertex
# configuration leaves only one possibility. All arithmetic is exact:
# every edge direction is a multiple of 30 degrees (45 for the truncated
# square tiling), so each coordinate is (a + b*sqrt(r))/2 with integer
# a, b and r = 3 (or 2). A vertex id is ((ax, bx), (ay, by)).

_ARCH_CONFIGS = {
    "elongated": ((3, 3, 3, 4, 4), 12),
    "snubsquare": ((3, 3, 4, 3, 4), 12),
    "kagome": ((3, 6, 3, 6), 12),
    "snubhex": ((3, 3, 3, 3, 6), 12),
    "truncsquare": ((4, 8, 8), 8),
    "trunchex": ((3, 12, 12), 12),
}


def _arch_directions(n_slots: int) -> list:
    """Exact unit vectors for each direction index: components are
    (a, b) meaning (a + b*sqrt(r))/2."""
    if n_slots == 12:  # 30-degree steps, sqrt(3)
        cos = [(2, 0), (0, 1), (1, 0), (0, 0), (-1, 0), (0, -1),
               (-2, 0), (0, -1), (-1, 0), (0, 0), (1, 0), (0, 1)]
        quarter = 3
    else:  # 8 slots: 45-degree steps, sqrt(2)
        cos = [(2, 0), (0, 1), (0, 0), (0, -1),
               (-2, 0), (0, -1), (0, 0), (0, 1)]
        quarter = 2
    sin = [cos[(k - quarter) % n_slots] for k in range(n_slots)]
    return [(cos[k], sin[k]) for k in range(n_slots)]


def _arch_interior_slots(size: int, n_slots: int) -> int:
    # interior angle of a regular size-gon, in slot units
    return n_slots * (size - 2) // (2 * size)


class _ArchimedeanTiler:
    """Grows a uniform tiling from its vertex configuration."""

    def __init__(self, config: tuple[int, ...], n_slots: int) -> None:
        self.config = config
        self.n_slots = n_slots
        self.radical = 3.0**0.5 if n_slots == 12 else 2.0**0.5
        self.directions = _arch_directions(n_slots)
        self.faces: list[tuple[int, list]] = []  # (size, vertex ids)
        self._seen_faces: set = set()
        self._occupancy: dict = {}  # vertex -> per-slot (face index, size)
        self._pending: dict = {}  # insertion-ordered set of vertices

    def position(self, vertex) -> tuple[float, float]:
        (ax, bx), (ay, by) = vertex
        return ((ax + bx * self.radical) / 2, (ay + by * self.radical) / 2)

    def _walk(self, start, direction: int, size: int) -> list:
        exterior = self.n_slots // 2 - _arch_interior_slots(size, self.n_slots)
        points = [start]
        current, d = start, direction
        for _ in range(size - 1):
            (ax, bx), (ay, by) = current
            (cx, dx), (cy, dy) = self.directions[d]
            current = ((ax + cx, bx + dx), (ay + cy, by + dy))
            points.append(current)
            d = (d + exterior) % self.n_slots
        return points

    def place(self, start, direction: int, size: int) -> None:
        """Add the size-gon whose first vertex is ``start`` with its first
        edge along ``direction`` (interior on the left)."""
        points = self._walk(start, direction, size)
        face_key = tuple(sorted(points))
        if face_key in self._seen_faces:
            return
        self._seen_faces.add(face_key)
        face_index = len(self.faces)
        self.faces.append((size, points))
        interior = _arch_interior_slots(size, self.n_slots)
        exterior = self.n_slots // 2 - interior
        for i, vertex in enumerate(points):
            out_dir = (direction + i * exterior) % self.n_slots
            slots = self._occupancy.setdefault(vertex, [None] * self.n_slots)
            for j in range(interior):
                slot = (out_dir + j) % self.n_slots
                if slots[slot] is not None:
                    raise ValueError(f"overlapping polygons at {vertex}")
                slots[slot] = (face_index, size)
            self._pending[vertex] = None

    def _resolve(self, vertex) -> bool:
        """Fill one determined gap at ``vertex``. True if a polygon was
        placed."""
        slots = self._occupancy[vertex]
        if None not in slots:
            self._pending.pop(vertex, None)
            return False
        n = self.n_slots
        targets = [
            s
            for s in range(n)
            if slots[s] is None
            and (slots[s - 1] is not None or slots[(s + 1) % n] is not None)
        ]
        if not targets:
            return False
        # every consistent way of laying the vertex configuration around
        # this vertex, respecting the polygons already placed
        layouts = []
        k = len(self.config)
        for rotation in range(k):
            sequence = self.config[rotation:] + self.config[:rotation]
            widths = [_arch_interior_slots(size, n) for size in sequence]
            for offset in range(n):
                owner = [None] * n  # slot -> (ordinal, size)
                starts = []
                position = offset
                for ordinal, size in enumerate(sequence):
                    starts.append(position % n)
                    for j in range(widths[ordinal]):
                        owner[(position + j) % n] = (ordinal, size)
                    position += widths[ordinal]
                consistent = True
                ordinal_face: dict[int, int] = {}
                face_ordinal: dict[int, int] = {}
                for s in range(n):
                    entry = slots[s]
                    if entry is None:
                        continue
                    face, face_size = entry
                    ordinal, size = owner[s]
                    if size != face_size:
                        consistent = False
                        break
                    if ordinal_face.setdefault(ordinal, face) != face:
                        consistent = False
                        break
                    if face_ordinal.setdefault(face, ordinal) != ordinal:
                        consistent = False
                        break
                if consistent:
                    layouts.append((owner, starts))
        # place any polygon whose position all layouts agree on
        for target in targets:
            candidates = {
                (owner[target][1], starts[owner[target][0]])
                for owner, starts in layouts
            }
            if len(candidates) == 1:
                size, start = candidates.pop()
                self.place(vertex, start, size)
                return True
        return False

    def grow(self, radius: float) -> None:
        origin = ((0, 0), (0, 0))
        cursor = 0
        for size in self.config:  # seed: the full star around the origin
            self.place(origin, cursor, size)
            cursor += _arch_interior_slots(size, self.n_slots)
        process_radius = radius + 2
        progressed = True
        while progressed:
            progressed = False
            for vertex in list(self._pending):
                x, y = self.position(vertex)
                if x * x + y * y > process_radius * process_radius:
                    self._pending.pop(vertex, None)
                    continue
                if self._resolve(vertex):
                    progressed = True
        for vertex, slots in self._occupancy.items():
            x, y = self.position(vertex)
            if x * x + y * y <= radius * radius and None in slots:
                raise RuntimeError(f"could not complete tiling at {vertex}")


def _snubhex_patch(radius: float) -> tuple[dict, callable]:
    """The snub hexagonal tiling (3.3.3.3.6) is not locally forced, so
    the constraint engine cannot grow it; build it directly instead.

    Hexagon centers occupy a sqrt(7) superlattice of the triangular
    lattice (basis (5,1) and (1,3) in half-side/row-height units): every
    other lattice vertex then touches exactly one hexagon, which is the
    3.3.3.3.6 vertex figure. Each small triangle with a hexagon-center
    vertex belongs to that hexagon; the rest are triangle cells.
    """
    height = ROOT3 / 2

    def position(vertex):
        return (vertex[0] / 2, vertex[1] * height)

    def hex_center(vertex):
        dx, dy = vertex[0] - 1, vertex[1]
        m, n = 3 * dx - dy, 5 * dy - dx
        if m % 14 or n % 14:
            return None
        return (m // 14, n // 14)

    cells: dict[Cell, list] = {}
    span = int(radius) + 4
    for row in range(-span, span):
        for i in range(-2 * span, 2 * span):
            points = _triangle_vertices(i, row, up=(row + i) % 2 == 0)
            if any(hex_center(p) is not None for p in points):
                continue  # part of a hexagon (or a dropped rim hexagon)
            xs, ys = zip(*(position(p) for p in points))
            cx, cy = sum(xs) / 3, sum(ys) / 3
            if cx * cx + cy * cy <= radius * radius:
                cells[(3, (row, i))] = points
    ring = [(2, 0), (1, 1), (-1, 1), (-2, 0), (-1, -1), (1, -1)]
    for m in range(-span, span):
        for n in range(-span, span):
            center = (1 + 5 * m + n, m + 3 * n)
            x, y = position(center)
            if x * x + y * y <= radius * radius:
                cells[(6, (m, n))] = [
                    (center[0] + ox, center[1] + oy) for ox, oy in ring
                ]
    return cells, position


def archimedean_board(
    mode: str, radius: float, mine_count: int, scale: float = 40
) -> Board:
    """A disc of an Archimedean tiling: all tiles whose center lies
    within ``radius`` edge lengths of the seed vertex."""
    if mode == "snubhex":
        cells, position = _snubhex_patch(radius)
    else:
        config, n_slots = _ARCH_CONFIGS[mode]
        tiler = _ArchimedeanTiler(config, n_slots)
        tiler.grow(radius)
        position = tiler.position
        cells = {}
        for index, (size, points) in enumerate(tiler.faces):
            xs, ys = zip(*(position(p) for p in points))
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            if cx * cx + cy * cy <= radius * radius:
                cells[(size, index)] = points

    adjacency = _shared_vertex_adjacency(cells)
    xy = {key: position(key) for quad in cells.values() for key in quad}
    min_x = min(x for x, _ in xy.values())
    min_y = min(y for _, y in xy.values())
    polygons = {
        cell: [((x - min_x) * scale, (y - min_y) * scale) for x, y in (xy[k] for k in keys)]
        for cell, keys in cells.items()
    }
    width = max(x for polygon in polygons.values() for x, _ in polygon)
    height = max(y for polygon in polygons.values() for _, y in polygon)
    return Board(mode, polygons, adjacency, mine_count, width, height)


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


def _tetrahedron() -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    """A regular tetrahedron: four vertices on alternate cube corners,
    the four faces being the four vertex triples. Winding is arbitrary
    (each subdivided cell is re-oriented outward on assembly)."""
    vertices: list[Vec3] = [(1.0, 1.0, 1.0), (1.0, -1.0, -1.0),
                            (-1.0, 1.0, -1.0), (-1.0, -1.0, 1.0)]
    faces = [(1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)]
    return vertices, faces


def _convex_board3d(
    mode: str, cells, positions, mine_count: int, radius: float = 1.0
) -> Board3D:
    """Assemble a closed convex board, orienting each polygon outward by
    its centroid direction. Correct for any convex solid that contains the
    origin (sphere, cube, tetrahedron): every surface point has a positive
    dot with its face's outward normal."""
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        polygons[cell] = _orient_outward(polygon, centroid)
    return Board3D(mode, polygons, adjacency, mine_count, radius=radius)


# -- 3D builders --------------------------------------------------------------


def _gyro_pentagons() -> tuple[dict, dict]:
    """The pentagonal hexecontahedron as (cells, vertex positions):
    the Conway "gyro" operation on an icosahedron — each triangular
    face gains a center vertex, each edge two division points, and
    every (face, corner) pair becomes one pentagon."""
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
    return cells, positions


def sphere_board(mine_count: int) -> Board3D:
    """A sphere tiled with 60 pentagons (a pentagonal hexecontahedron,
    projected onto the unit sphere). Every pentagon has exactly 7
    neighbors."""
    cells, positions = _gyro_pentagons()
    return _convex_board3d("sphere", cells, positions, mine_count)


def snub_dodecahedron_board(mine_count: int) -> Board3D:
    """A snub dodecahedron: 12 pentagons and 80 triangles (vertex
    configuration 3.3.3.3.5), projected onto the unit sphere.

    Built as the dual of the pentagonal hexecontahedron: one cell per
    hexecontahedron vertex, made of the surrounding pentagon centers.
    """
    pentagons, positions = _gyro_pentagons()
    centers = {
        cid: _normalize(
            tuple(
                sum(positions[k][axis] for k in keys) / len(keys)
                for axis in range(3)
            )
        )
        for cid, keys in pentagons.items()
    }
    around: dict[Hashable, list] = defaultdict(list)
    for cid, keys in pentagons.items():
        for key in keys:
            around[key].append(cid)
    cells = {
        key: _tangent_order(positions[key], [(cid, centers[cid]) for cid in ids])
        for key, ids in around.items()
    }
    return _convex_board3d("snubdodec", cells, centers, mine_count)


def _geodesic(
    frequency: int, vertices=None, faces=None, project: bool = True
) -> tuple[dict, list[tuple]]:
    """Subdivide each triangular face into ``frequency**2`` triangles.
    Defaults to the icosahedron; ``project`` normalizes vertices onto the
    unit sphere (a geodesic icosahedron), otherwise they stay on the flat
    faces (e.g. a triangulated tetrahedron).

    Returns (positions, triangles). Vertex keys are gcd-normalized
    barycentric weights over the corners, so vertices on shared edges
    match exactly across faces.
    """
    if vertices is None or faces is None:
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
                point = tuple(
                    sum(w * c[axis] for w, c in zip(weights, corners)) / frequency
                    for axis in range(3)
                )
                positions[vertex_key] = _normalize(point) if project else point
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
    return _convex_board3d(mode, cells, centers, mine_count)


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
    return _convex_board3d("spheretri", cells, positions, mine_count)


def cube_board(n: int, mine_count: int) -> Board3D:
    """A cube surface tiled with ``6 * n**2`` squares: each face an n x n
    grid. Vertices are integer points on ``[-n, n]**3`` (a surface vertex
    has one axis at +-n; the grid lines step by 2), so cells on adjacent
    faces sharing a cube edge or corner become neighbors automatically."""
    cells: dict[Cell, list] = {}
    positions: dict[Hashable, Vec3] = {}
    for axis in range(3):
        u_axis, v_axis = (a for a in range(3) if a != axis)
        for sign in (-1, 1):
            for i in range(n):
                for j in range(n):
                    keys = []
                    for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        coord = [0, 0, 0]
                        coord[axis] = sign * n
                        coord[u_axis] = -n + 2 * (i + du)
                        coord[v_axis] = -n + 2 * (j + dv)
                        key = tuple(coord)
                        keys.append(key)
                        if key not in positions:
                            positions[key] = (key[0] / n, key[1] / n, key[2] / n)
                    cells[(axis, sign, i, j)] = keys
    return _convex_board3d("cube", cells, positions, mine_count, radius=ROOT3)


def _polycube_board3d(mode, cells, positions, mine_count, radius) -> Board3D:
    """Assemble a closed but non-convex polycube surface. Each cell is a
    unit square already wound outward by the builder (its outward normal
    is known from which cube face it is), so — unlike ``_convex_board3d``
    — orientation is not inferred from the centroid direction, which is
    wrong for the inward-facing tunnel walls."""
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(mode, polygons, adjacency, mine_count, radius=radius)


def _polycube_surface(mode, solid, extent, mine_count) -> Board3D:
    """The boundary of a polycube (a union of axis-aligned unit cubes),
    tiled by unit squares. ``solid(i, j, k)`` says whether the unit cube
    at integer indices is filled; ``extent`` is the ``(nx, ny, nz)``
    bounding box. Cubes are scaled uniformly and centered in ``[-1, 1]``.

    A unit square is a cell exactly when it separates a filled cube from
    empty space, and it is wound so its normal points outward (out of the
    filled cube) — which, unlike the centroid rule ``_convex_board3d``
    uses, is also correct for the concave step shoulders and inner walls
    these solids have. Vertices are the integer lattice points, so faces
    meeting at an edge or corner share vertex ids and become neighbors."""
    nx, ny, nz = extent
    center = (nx / 2, ny / 2, nz / 2)
    scale = 2.0 / max(extent)

    def position(p) -> Vec3:
        return tuple((c - o) * scale for c, o in zip(p, center))

    def filled(i: int, j: int, k: int) -> bool:
        return 0 <= i < nx and 0 <= j < ny and 0 <= k < nz and solid(i, j, k)

    cells: dict[Cell, list] = {}
    positions: dict[Hashable, Vec3] = {}
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if not solid(i, j, k):
                    continue
                for axis in range(3):
                    for sign in (-1, 1):
                        step = [0, 0, 0]
                        step[axis] = sign
                        if filled(i + step[0], j + step[1], k + step[2]):
                            continue  # interior face, not on the boundary
                        base = [i, j, k]
                        if sign > 0:
                            base[axis] += 1  # the far face of the cube
                        u_axis, v_axis = (a for a in range(3) if a != axis)
                        corners = []
                        for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                            p = list(base)
                            p[u_axis] += du
                            p[v_axis] += dv
                            corners.append(tuple(p))
                        outward = [0.0, 0.0, 0.0]
                        outward[axis] = float(sign)
                        pts = [position(p) for p in corners]
                        if _dot(newell_normal(pts), tuple(outward)) <= 0:
                            corners.reverse()
                        for p in corners:
                            positions.setdefault(p, position(p))
                        cells[(i, j, k, axis, sign)] = corners
    radius = max(math.hypot(*p) for p in positions.values())
    return _polycube_board3d(mode, cells, positions, mine_count, radius=radius)


def cube_frame_board(n: int, thickness: int, mine_count: int) -> Board3D:
    """The surface of a cube frame (a level-1 Menger sponge): an
    ``n x n x n`` stack of unit cubes with an ``(n - 2*thickness)`` cube
    bored out of the middle of each face, meeting in a hollow centre. What
    is left are the twelve edge bars plus eight corners — a genus-5 solid
    whose whole boundary is tiled by unit squares.

    A unit cube is kept when at least two of its three coordinates lie in
    the outer band (within ``thickness`` of a face)."""
    if not (thickness >= 1 and 2 * thickness < n):
        raise ValueError("thickness must be >= 1 and leave a non-empty hole")

    def outer(c: int) -> bool:
        return c < thickness or c >= n - thickness

    def solid(i: int, j: int, k: int) -> bool:
        return (outer(i) + outer(j) + outer(k)) >= 2

    return _polycube_surface("cubeframe", solid, (n, n, n), mine_count)


def stepped_bipyramid_board(base: int, levels: int, mine_count: int) -> Board3D:
    """A stepped bipyramid: a stepped pyramid of square terraces stitched
    base-to-base with its z-mirror image (the shared biggest terrace kept
    only once). Square layer ``d`` steps from the middle has side
    ``base - 2*d``, so the solid is widest at the equator and tapers to a
    small square top and bottom — a terraced diamond whose staircase
    surface (concave at every shoulder) is tiled by unit squares.

    ``levels`` counts the terraces of one pyramid; the apex square has
    side ``base - 2*(levels - 1)`` and the whole stack is ``2*levels - 1``
    layers tall."""
    if not (levels >= 2 and base - 2 * (levels - 1) >= 1):
        raise ValueError("need levels >= 2 and a positive apex square")
    height = 2 * levels - 1
    middle = levels - 1  # the z-index of the biggest (equator) terrace

    def solid(i: int, j: int, k: int) -> bool:
        margin = abs(k - middle)  # each step in from the equator shrinks by 1
        return margin <= i < base - margin and margin <= j < base - margin

    return _polycube_surface("steppedbipyramid", solid, (base, base, height), mine_count)


def tetrahedron_board(mine_count: int, frequency: int = 4) -> Board3D:
    """A regular tetrahedron tiled with triangles: each of the 4 faces
    subdivided into ``frequency**2`` cells, kept flat on the faces."""
    vertices, faces = _tetrahedron()
    positions, triangles = _geodesic(frequency, vertices, faces, project=False)
    cells = {("t", n): list(triangle) for n, triangle in enumerate(triangles)}
    radius = max(math.hypot(*p) for p in positions.values())
    return _convex_board3d("tetrahedron", cells, positions, mine_count, radius=radius)


def tetrahedron_frame_board(mine_count: int, frequency: int = 4) -> Board3D:
    """A level-1 Sierpiński tetrahedron: midpoint-subdividing a regular
    tetrahedron splits it into four corner sub-tetrahedra plus a central
    octahedron, and the octahedron is carved out. What is left are the four
    half-scale corner tetrahedra, meeting only at the six edge-midpoints of
    the original — so on each original face the middle triangle is gone. Each
    sub-tetrahedron face is subdivided into ``frequency**2`` flat triangles.

    Non-convex (the inward faces point toward the hollow centre), so unlike
    ``tetrahedron_board`` each triangle is oriented outward from its own
    sub-tetrahedron's centroid rather than the origin."""
    base, _ = _tetrahedron()
    # Ten shared points: the 4 original corners, then the 6 edge midpoints.
    # A single global vertex list keeps the midpoints' subdivision keys
    # identical across the two sub-tetrahedra that meet at them.
    verts = list(base)
    mid_index: dict[tuple[int, int], int] = {}
    for a in range(4):
        for b in range(a + 1, 4):
            mid_index[(a, b)] = len(verts)
            verts.append(tuple((base[a][axis] + base[b][axis]) / 2 for axis in range(3)))

    cells: dict[Cell, list] = {}
    positions: dict[Hashable, Vec3] = {}
    centroids: dict[Cell, Vec3] = {}
    for corner in range(4):
        others = [j for j in range(4) if j != corner]
        tet = [corner] + [mid_index[tuple(sorted((corner, j)))] for j in others]
        centroid = tuple(sum(verts[v][axis] for v in tet) / 4 for axis in range(3))
        faces = [
            (tet[1], tet[2], tet[3]),
            (tet[0], tet[2], tet[3]),
            (tet[0], tet[1], tet[3]),
            (tet[0], tet[1], tet[2]),
        ]
        pos, triangles = _geodesic(frequency, verts, faces, project=False)
        positions.update(pos)
        for n, triangle in enumerate(triangles):
            cell = (corner, n)
            cells[cell] = list(triangle)
            centroids[cell] = centroid

    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        face_centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        outward = tuple(f - c for f, c in zip(face_centroid, centroids[cell]))
        polygons[cell] = _orient_outward(polygon, outward)
    radius = max(math.hypot(*p) for p in positions.values())
    return Board3D("tetraframe", polygons, adjacency, mine_count, radius=radius)


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


# -- Archimedean tilings on wrapped surfaces ---------------------------------
#
# Each two-shape tiling is reduced to one rectangular fundamental domain
# (a template): vertices canonicalized into the domain, cells as references
# into this or neighboring domain copies. Wrapping is then the same modular
# arithmetic the square/triangle/hex surface boards use, with the whole
# template as the repeating unit.


@dataclass(frozen=True)
class _ArchTemplate:
    config: tuple[int, ...]  # vertex configuration, e.g. (3, 6, 3, 6)
    width: float  # domain size in edge lengths
    height: float
    verts: dict  # tag -> (x, y) position within the domain
    cells: tuple  # (name, ((tag, dm, dn), ...)); dm/dn = domain copy offset
    mirror: dict | None  # tag -> (tag, dm, dn) under y -> height - y
    glide: bool = False  # the mirror needs an extra width/2 x-shift (p4g)


def _template(config, width, height, polygons, mirrored=True, glide=False):
    """Build a template from one domain's worth of cell polygons in float
    coordinates. Each vertex is canonicalized into [0, width) x [0, height);
    the rounded canonical position doubles as its exact hashable tag."""

    def reduce(value: float, size: float) -> tuple[float, int]:
        # the slack absorbs tag rounding, so values that are exactly on a
        # domain edge land on its near side; real vertices are never this
        # close to an edge without being on it
        d = math.floor(value / size + 1e-5)
        return round(value - d * size, 6) + 0.0, d  # + 0.0 turns -0.0 into 0.0

    def canonical(x: float, y: float):
        (rx, dm), (ry, dn) = reduce(x, width), reduce(y, height)
        return (rx, ry), dm, dn

    verts = {}
    cells = []
    for name, polygon in polygons:
        refs = []
        for x, y in polygon:
            tag, dm, dn = canonical(x, y)
            verts[tag] = tag
            refs.append((tag, dm, dn))
        # normalize so the cell's centroid lies in domain copy (0, 0):
        # the Möbius builder selects cell instances by centroid
        cx = sum(dm * width + tag[0] for tag, dm, _ in refs) / len(refs)
        cy = sum(dn * height + tag[1] for tag, _, dn in refs) / len(refs)
        mshift = math.floor(cx / width + 1e-9)
        nshift = math.floor(cy / height + 1e-9)
        refs = [(tag, dm - mshift, dn - nshift) for tag, dm, dn in refs]
        cells.append((name, tuple(refs)))

    def wrap_gap(delta: float, size: float) -> float:
        delta = abs(delta) % size
        return min(delta, size - delta)

    def distance(tag, x: float, y: float) -> float:
        return math.hypot(wrap_gap(tag[0] - x, width), wrap_gap(tag[1] - y, height))

    mirror = None
    if mirrored:
        shift = width / 2 if glide else 0.0
        mirror = {}
        for tag in verts:
            x, y = tag[0] + shift, height - tag[1]
            image, dm, dn = canonical(x, y)
            if image not in verts:
                # tags are rounded; match the closest vertex (wrap-aware)
                image = min(verts, key=lambda v: distance(v, x, y))
                if distance(image, x, y) > 1e-4:
                    raise ValueError(f"mirror of {tag} is not a vertex")
            mirror[tag] = (image, dm, dn)
    return _ArchTemplate(config, width, height, verts, tuple(cells), mirror, glide)


def _kagome_template() -> _ArchTemplate:
    """Kagome (3.6.3.6): hexagon centers on a side-2 triangular lattice,
    cell vertices at the lattice edge midpoints. The 2 x 2*sqrt(3)
    rectangle holds two hexagons and four triangles."""
    h = ROOT3 / 2

    def hexagon(cx, cy):
        return [(cx + 1, cy), (cx + 0.5, cy + h), (cx - 0.5, cy + h),
                (cx - 1, cy), (cx - 0.5, cy - h), (cx + 0.5, cy - h)]

    polygons = [
        ("hex0", hexagon(0.0, 0.0)),
        ("hex1", hexagon(1.0, ROOT3)),
        # midpoint triangles of the four lattice faces per domain
        ("tri0", [(1, 0), (1.5, h), (0.5, h)]),
        ("tri1", [(1.5, h), (2, ROOT3), (2.5, h)]),
        ("tri2", [(2, ROOT3), (2.5, ROOT3 + h), (1.5, ROOT3 + h)]),
        ("tri3", [(1.5, ROOT3 + h), (1, 2 * ROOT3), (0.5, ROOT3 + h)]),
    ]
    return _template((3, 6, 3, 6), 2.0, 2 * ROOT3, polygons)


def _truncsquare_template() -> _ArchTemplate:
    """Truncated square (4.8.8): octagons on a square lattice of pitch
    1 + sqrt(2), tilted unit squares filling the corners between them."""
    a = 1 + 2**0.5  # lattice pitch
    p, q = a / 2, 2**0.5 / 2
    octagon = [(0.5, p), (p, 0.5), (p, -0.5), (0.5, -p),
               (-0.5, -p), (-p, -0.5), (-p, 0.5), (-0.5, p)]
    square = [(p - q, p), (p, p - q), (p + q, p), (p, p + q)]
    return _template((4, 8, 8), a, a, [("oct", octagon), ("sq", square)])


def _elongated_template() -> _ArchTemplate:
    """Elongated triangular (3.3.3.4.4): rows of squares separated by rows
    of triangles, consecutive square rows offset by half a square. The
    domain is one square wide and two rows tall, starting at a square
    row's centerline so that the template midline (through the other
    square row) is a mirror line, which the Möbius seam needs."""
    h = ROOT3 / 2
    polygons = [
        ("sq0", [(0, -0.5), (1, -0.5), (1, 0.5), (0, 0.5)]),
        ("tri0", [(0, 0.5), (1, 0.5), (0.5, 0.5 + h)]),
        ("tri1", [(0.5, 0.5 + h), (1, 0.5), (1.5, 0.5 + h)]),
        ("sq1", [(0.5, 0.5 + h), (1.5, 0.5 + h), (1.5, 1.5 + h), (0.5, 1.5 + h)]),
        ("tri2", [(0.5, 1.5 + h), (1.5, 1.5 + h), (1, 1.5 + 2 * h)]),
        ("tri3", [(1, 1.5 + 2 * h), (1.5, 1.5 + h), (2, 1.5 + 2 * h)]),
    ]
    return _template((3, 3, 3, 4, 4), 1.0, 2 + ROOT3, polygons)


def _snubsquare_template() -> _ArchTemplate:
    """Snub square (3.3.4.3.4): squares alternately rotated +-15 degrees
    on a square lattice of pitch sqrt(2+sqrt(3)), pairs of triangles
    between them. p4g has no plain horizontal mirror, only a glide
    (mirror plus half a period), so the template is aligned with the
    glide axis on its midline and marked glide=True."""
    a = (2 + ROOT3) ** 0.5
    r = 2**-0.5

    def square(cx, cy, first_corner):
        return [(cx + r * math.cos(math.radians(first_corner + 90 * k)),
                 cy + r * math.sin(math.radians(first_corner + 90 * k)))
                for k in range(4)]

    def tri_on(points, center, k):
        # the equilateral triangle on edge k of a square, apex away from it
        (x1, y1), (x2, y2) = points[k], points[(k + 1) % 4]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        apex = (mx + ROOT3 * (mx - center[0]), my + ROOT3 * (my - center[1]))
        return [(x1, y1), (x2, y2), apex]

    plus = square(0, a / 4, 60)  # rotated +15
    minus = square(a / 2, 3 * a / 4, 30)  # rotated -15
    polygons = [
        ("sq0", plus),
        ("sq1", minus),
        ("tri0", tri_on(plus, (0, a / 4), 0)),
        ("tri1", tri_on(plus, (0, a / 4), 2)),
        ("tri2", tri_on(minus, (a / 2, 3 * a / 4), 0)),
        ("tri3", tri_on(minus, (a / 2, 3 * a / 4), 2)),
    ]
    return _template((3, 3, 4, 3, 4), a, a, polygons, glide=True)


def _snubhex_template() -> _ArchTemplate:
    """Snub hexagonal (3.3.3.3.6) on the rotated rectangle spanned by the
    orthogonal superlattice vectors (5,1) and (3,-5) (in the half-side /
    row-height units of _snubhex_patch): sqrt(7) x sqrt(21) edge lengths
    holding two hexagons and sixteen triangles. The tiling is chiral
    (p6: no mirror, no glide), so it cannot wrap a Möbius strip; there
    is deliberately no mirror map."""
    width, height = 7**0.5, 21**0.5

    def uv(x, row):
        # coordinates along the two orthogonal superlattice directions
        return ((5 * x + 3 * row) / (4 * width), 3 * (x - 5 * row) / (4 * height))

    def hex_center(x, row):
        m, n = 3 * (x - 1) - row, 5 * row - (x - 1)
        if m % 14 or n % 14:
            return None
        return (m // 14, n // 14)

    def in_domain(points):
        cu = sum(u for u, _ in points) / len(points)
        cv = sum(v for _, v in points) / len(points)
        return -1e-9 <= cu < width - 1e-9 and -1e-9 <= cv < height - 1e-9

    polygons = []
    for row in range(-7, 4):
        for i in range(-3, 11):
            corners = _triangle_vertices(i, row, up=(row + i) % 2 == 0)
            if any(hex_center(*p) is not None for p in corners):
                continue  # part of a hexagon
            points = [uv(*p) for p in corners]
            if in_domain(points):
                polygons.append((f"t{row},{i}", points))
    ring = [(2, 0), (1, 1), (-1, 1), (-2, 0), (-1, -1), (1, -1)]
    for m in range(-3, 4):
        for n in range(-3, 4):
            cx, crow = 1 + 5 * m + n, m + 3 * n
            points = [uv(cx + ox, crow + oy) for ox, oy in ring]
            if in_domain(points):
                polygons.append((f"h{m},{n}", points))
    return _template((3, 3, 3, 3, 6), width, height, polygons, mirrored=False)


def _trunchex_template() -> _ArchTemplate:
    """Truncated hexagonal (3.12.12): dodecagons on a hexagonal lattice of
    pitch 2+sqrt(3), up/down triangles between them. The conventional
    rectangle holds two dodecagons and four triangles."""
    a = 2 + ROOT3
    r = (6**0.5 + 2**0.5) / 2  # dodecagon circumradius, side 1
    e = 0.5 + ROOT3 / 2

    def around(cx, cy, suffix):
        dodecagon = [(cx + r * math.cos(math.radians(15 + 30 * k)),
                      cy + r * math.sin(math.radians(15 + 30 * k)))
                     for k in range(12)]
        return [
            ("dod" + suffix, dodecagon),
            # the up and the down triangle right of this dodecagon
            ("up" + suffix, [(cx + a / 2, cy + 0.5), (cx + a - e, cy + e),
                             (cx + e, cy + e)]),
            ("down" + suffix, [(cx + a / 2, cy - 0.5), (cx + e, cy - e),
                               (cx + a - e, cy - e)]),
        ]

    polygons = around(0, 0, "0") + around(a / 2, a * ROOT3 / 2, "1")
    return _template((3, 12, 12), a, a * ROOT3, polygons)


_ARCH_TEMPLATES = {
    "elongated": _elongated_template,
    "snubsquare": _snubsquare_template,
    "kagome": _kagome_template,
    "snubhex": _snubhex_template,
    "truncsquare": _truncsquare_template,
    "trunchex": _trunchex_template,
}


@lru_cache(maxsize=None)
def _arch_template(tiling: str) -> _ArchTemplate:
    return _ARCH_TEMPLATES[tiling]()


def _arch_cells(template, nx: int, ny: int, tiling: str, wrap_rows: bool = True):
    """All cells of an nx x ny grid of domain copies, vertex keys wrapped
    modulo the grid: key = (domain column, domain row, tag). Rows stay
    unwrapped for open-ended surfaces (cylinder)."""
    cells = {}
    for m in range(nx):
        for n in range(ny):
            for name, refs in template.cells:
                keys = [((m + dm) % nx, (n + dn) % ny if wrap_rows else n + dn, tag)
                        for tag, dm, dn in refs]
                if len(set(keys)) < len(keys):  # a cell met its own wrap
                    raise ValueError(f"{nx}x{ny} is too small for {tiling}")
                cells[(m, n, name)] = keys
    return cells


def arch_torus_board(
    tiling: str, nx: int, ny: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """An Archimedean tiling wrapped around a donut: ``nx`` domain copies
    around the ring, ``ny`` around the tube."""
    template = _arch_template(tiling)
    ring = nx * template.width
    tube = ny * template.height

    def position(m: int, n: int, tag) -> Vec3:
        vx, vy = template.verts[tag]
        theta = 2 * math.pi * (m * template.width + vx) / ring
        phi = 2 * math.pi * (n * template.height + vy) / tube
        radial = 1.0 + tube_radius * math.cos(phi)
        return (
            radial * math.cos(theta),
            radial * math.sin(theta),
            tube_radius * math.sin(phi),
        )

    cells = _arch_cells(template, nx, ny, tiling)
    positions = {key: position(*key) for keys in cells.values() for key in keys}
    return _torus_oriented(
        "torus" + tiling, positions, cells, mine_count, radius=1.0 + tube_radius
    )


def _assemble_two_sided(mode, cells, positions, mine_count, radius) -> Board3D:
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        mode, polygons, adjacency, mine_count, radius=radius, two_sided=True
    )


def arch_cylinder_board(
    tiling: str, ring: int, rows: float, mine_count: int, cut: float = 0.0
) -> Board3D:
    """An Archimedean tiling around the side of a cylinder: ``ring``
    domain copies around, ``rows`` up the axis, open ends. ``cut``
    shifts where the strip starts within the repeating rows and ``rows``
    may be fractional: along a tiling's horizontal edge-lines these make
    the rims flat. Tilings without such lines (the snubs) get a clean
    but zigzag rim: cells are only ever whole."""
    template = _arch_template(tiling)
    height = template.height
    unit = 2 * math.pi / (ring * template.width)  # arc length of one edge unit
    middle = rows * height / 2 + cut

    def position(m: int, n: int, tag) -> Vec3:
        vx, vy = template.verts[tag]
        theta = (m * template.width + vx) * unit
        return (
            math.cos(theta),
            (n * height + vy - middle) * unit,
            math.sin(theta),
        )

    centroids = {
        name: sum(dn * height + template.verts[tag][1] for tag, _, dn in refs)
        / len(refs)
        for name, refs in template.cells
    }
    cells = {}
    for m in range(ring):
        for n in range(math.ceil(rows) + 1):
            for name, refs in template.cells:
                if not cut - 1e-9 <= centroids[name] + n * height < rows * height + cut - 1e-9:
                    continue  # this row copy of the cell is outside the strip
                keys = [((m + dm) % ring, n + dn, tag) for tag, dm, dn in refs]
                if len(set(keys)) < len(keys):
                    raise ValueError(f"ring {ring} is too small for {tiling}")
                cells[(m, n, name)] = keys
    positions = {key: position(*key) for keys in cells.values() for key in keys}
    return _assemble_two_sided(
        "cyl" + tiling, cells, positions, mine_count,
        radius=max(math.hypot(*p) for p in positions.values()),
    )


def arch_mobius_board(tiling: str, ring: int, rows: int, mine_count: int) -> Board3D:
    """An Archimedean tiling on a Möbius strip: ``ring`` domain copies
    around, ``rows`` across; after a full loop the strip glues to its
    start flipped. The flip needs a horizontal mirror symmetry. p4g
    (snub square) only has a glide — mirror plus half a domain — so its
    ring counts half-domains and must be odd for the seam to close.
    3.3.3.3.6 (snub hexagonal) is chiral: no mirror, no glide, so no
    Möbius strip at all (its mirror image is a different tiling)."""
    template = _arch_template(tiling)
    if template.mirror is None:
        raise ValueError(f"{tiling} is chiral and cannot wrap a Möbius strip")
    if template.glide:
        if ring % 2 == 0:
            raise ValueError("ring counts half-domains and must be odd")
        halves = ring
    else:
        halves = 2 * ring
    width, height = template.width, template.height
    q, odd = divmod(halves, 2)
    length = halves * width / 2
    strip = rows * height
    half_width = min(0.7, math.pi * strip / length / 2)

    def flipped(mi: int, ni: int, tag):
        image, dm, dn = template.mirror[tag]
        return image, mi + dm - odd, rows - 1 - ni + dn

    def canonical(mi: int, ni: int, tag):
        # bring x = mi*width + vx into [0, length), flipping at the seam;
        # measured in half-domains, with slack for the rounded tags
        while 2 * mi + 2 * template.verts[tag][0] / width >= halves - 1e-5:
            tag, mi, ni = flipped(mi - q, ni, tag)
        while 2 * mi + 2 * template.verts[tag][0] / width < -1e-5:
            tag, mi, ni = flipped(mi + q + odd, ni, tag)
        return (mi, ni, tag)

    def position(mi: int, ni: int, tag) -> Vec3:
        vx, vy = template.verts[tag]
        u = 2 * math.pi * (mi * width + vx) / length
        v = half_width * (2 * (ni * height + vy) / strip - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (radial * math.cos(u), radial * math.sin(u), v * math.sin(u / 2))

    centroids = {
        name: sum(dm * width + template.verts[tag][0] for tag, dm, _ in refs)
        / len(refs)
        for name, refs in template.cells
    }
    cells = {}
    for m in range(q + 1):
        for n in range(rows):
            for name, refs in template.cells:
                if not -1e-9 <= centroids[name] + m * width < length - 1e-9:
                    continue  # this domain copy of the cell is past the seam
                keys = [canonical(m + dm, n + dn, tag) for tag, dm, dn in refs]
                if len(set(keys)) < len(keys):
                    raise ValueError(f"ring {ring} is too small for {tiling}")
                cells[(m, n, name)] = keys
    positions = {key: position(*key) for keys in cells.values() for key in keys}
    return _assemble_two_sided(
        "mobius" + tiling, cells, positions, mine_count,
        radius=max(math.hypot(*p) for p in positions.values()),
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
        "easy": lambda: penrose_board(4, 9, scale=310, keep=60),
        "medium": lambda: penrose_board(5, 25, scale=390, keep=160),
        "hard": lambda: penrose_board(6, 70, scale=495, keep=430),
    },
    "hat": {
        "easy": lambda: hat_board(2, 10, keep=64, scale=12),
        "medium": lambda: hat_board(3, 28, keep=150, scale=9.5),
        "hard": lambda: hat_board(3, 65, keep=430, scale=7),
    },
    "elongated": {
        "easy": lambda: archimedean_board("elongated", 4, 11, scale=62),
        "medium": lambda: archimedean_board("elongated", 5.8, 27, scale=41),
        "hard": lambda: archimedean_board("elongated", 8.2, 63, scale=29),
    },
    "snubsquare": {
        "easy": lambda: archimedean_board("snubsquare", 4, 11, scale=59),
        "medium": lambda: archimedean_board("snubsquare", 5.8, 28, scale=41),
        "hard": lambda: archimedean_board("snubsquare", 8.2, 62, scale=29),
    },
    "kagome": {
        "easy": lambda: archimedean_board("kagome", 5.5, 11, scale=45),
        "medium": lambda: archimedean_board("kagome", 8.5, 30, scale=29),
        "hard": lambda: archimedean_board("kagome", 11.5, 65, scale=21),
    },
    "snubhex": {
        "easy": lambda: archimedean_board("snubhex", 4.2, 12, scale=52),
        "medium": lambda: archimedean_board("snubhex", 6.3, 30, scale=38),
        "hard": lambda: archimedean_board("snubhex", 8.6, 64, scale=27),
    },
    "truncsquare": {
        "easy": lambda: archimedean_board("truncsquare", 8, 10, scale=31),
        "medium": lambda: archimedean_board("truncsquare", 13, 29, scale=19),
        "hard": lambda: archimedean_board("truncsquare", 17.5, 61, scale=14),
    },
    "trunchex": {
        "easy": lambda: archimedean_board("trunchex", 11, 13, scale=20.5),
        "medium": lambda: archimedean_board("trunchex", 16, 32, scale=15),
        "hard": lambda: archimedean_board("trunchex", 21, 64, scale=11.5),
    },
    "sphere": {
        "easy": lambda: sphere_board(7),
        "medium": lambda: sphere_board(10),
        "hard": lambda: sphere_board(14),
    },
    "snubdodec": {
        "easy": lambda: snub_dodecahedron_board(10),
        "medium": lambda: snub_dodecahedron_board(14),
        "hard": lambda: snub_dodecahedron_board(19),
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
    "cube": {
        "easy": lambda: cube_board(4, 12),
        "medium": lambda: cube_board(6, 38),
        "hard": lambda: cube_board(8, 84),
    },
    "tetrahedron": {
        "easy": lambda: tetrahedron_board(8, 4),
        "medium": lambda: tetrahedron_board(24, 6),
        "hard": lambda: tetrahedron_board(55, 8),
    },
    "tetraframe": {  # level-1 Sierpiński tetrahedron; 16 * frequency**2 cells
        "easy": lambda: tetrahedron_frame_board(8, 2),
        "medium": lambda: tetrahedron_frame_board(26, 3),
        "hard": lambda: tetrahedron_frame_board(54, 4),
    },
    "cubeframe": {  # n x n x n frame, thickness = hole = n / 3
        "easy": lambda: cube_frame_board(6, 2, 40),
        "medium": lambda: cube_frame_board(9, 3, 104),
        "hard": lambda: cube_frame_board(12, 4, 200),
    },
    "steppedbipyramid": {  # stepped bipyramid, base x base, `levels` terraces
        "easy": lambda: stepped_bipyramid_board(6, 3, 20),
        "medium": lambda: stepped_bipyramid_board(8, 4, 40),
        "hard": lambda: stepped_bipyramid_board(10, 5, 72),
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
    "toruselongated": {
        "easy": lambda: arch_torus_board("elongated", 12, 1, 9, 0.31),
        "medium": lambda: arch_torus_board("elongated", 14, 2, 26, 0.53),
        "hard": lambda: arch_torus_board("elongated", 20, 2, 48, 0.37),
    },
    "torussnubsquare": {
        "easy": lambda: arch_torus_board("snubsquare", 5, 2, 8, 0.40),
        "medium": lambda: arch_torus_board("snubsquare", 7, 3, 19, 0.43),
        "hard": lambda: arch_torus_board("snubsquare", 10, 4, 48, 0.40),
    },
    "toruskagome": {
        "easy": lambda: arch_torus_board("kagome", 8, 2, 12, 0.43),
        "medium": lambda: arch_torus_board("kagome", 10, 2, 18, 0.35),
        "hard": lambda: arch_torus_board("kagome", 12, 3, 43, 0.43),
    },
    "torussnubhex": {
        "easy": lambda: arch_torus_board("snubhex", 4, 1, 9, 0.43),
        "medium": lambda: arch_torus_board("snubhex", 6, 1, 16, 0.29),
        "hard": lambda: arch_torus_board("snubhex", 7, 2, 50, 0.49),
    },
    "torustruncsquare": {
        "easy": lambda: arch_torus_board("truncsquare", 9, 4, 9, 0.44),
        "medium": lambda: arch_torus_board("truncsquare", 12, 6, 22, 0.50),
        "hard": lambda: arch_torus_board("truncsquare", 16, 7, 45, 0.44),
    },
    "torustrunchex": {
        "easy": lambda: arch_torus_board("trunchex", 7, 2, 10, 0.49),
        "medium": lambda: arch_torus_board("trunchex", 10, 2, 18, 0.35),
        "hard": lambda: arch_torus_board("trunchex", 12, 3, 43, 0.43),
    },
    "mobiuselongated": {
        "easy": lambda: arch_mobius_board("elongated", 12, 1, 9),
        "medium": lambda: arch_mobius_board("elongated", 12, 2, 22),
        "hard": lambda: arch_mobius_board("elongated", 18, 2, 43),
    },
    "mobiussnubsquare": {
        "easy": lambda: arch_mobius_board("snubsquare", 13, 2, 10),
        "medium": lambda: arch_mobius_board("snubsquare", 15, 3, 20),
        "hard": lambda: arch_mobius_board("snubsquare", 17, 4, 41),
    },
    "mobiuskagome": {
        "easy": lambda: arch_mobius_board("kagome", 12, 1, 9),
        "medium": lambda: arch_mobius_board("kagome", 12, 2, 22),
        "hard": lambda: arch_mobius_board("kagome", 18, 2, 43),
    },
    "mobiustruncsquare": {
        "easy": lambda: arch_mobius_board("truncsquare", 12, 3, 9),
        "medium": lambda: arch_mobius_board("truncsquare", 16, 4, 19),
        "hard": lambda: arch_mobius_board("truncsquare", 22, 5, 44),
    },
    "mobiustrunchex": {
        "easy": lambda: arch_mobius_board("trunchex", 9, 1, 7),
        "medium": lambda: arch_mobius_board("trunchex", 10, 2, 18),
        "hard": lambda: arch_mobius_board("trunchex", 12, 3, 43),
    },
    # cylinder cuts: elongated ends on square rows (fractional rows adds
    # the closing row), kagome cuts along its horizontal edge-line, the
    # rest sit where their rims look best
    "cylelongated": {
        "easy": lambda: arch_cylinder_board(
            "elongated", 10, 1 + 1 / (2 + ROOT3), 8, cut=-0.5),
        "medium": lambda: arch_cylinder_board(
            "elongated", 12, 2 + 1 / (2 + ROOT3), 24, cut=-0.5),
        "hard": lambda: arch_cylinder_board(
            "elongated", 15, 3 + 1 / (2 + ROOT3), 60, cut=-0.5),
    },
    "cylsnubsquare": {
        "easy": lambda: arch_cylinder_board("snubsquare", 5, 2, 8),
        "medium": lambda: arch_cylinder_board("snubsquare", 7, 3, 19),
        "hard": lambda: arch_cylinder_board("snubsquare", 9, 5, 57),
    },
    "cylkagome": {
        "easy": lambda: arch_cylinder_board("kagome", 6, 2, 9, cut=ROOT3 / 2),
        "medium": lambda: arch_cylinder_board("kagome", 9, 3, 24, cut=ROOT3 / 2),
        "hard": lambda: arch_cylinder_board("kagome", 11, 4, 55, cut=ROOT3 / 2),
    },
    "cylsnubhex": {
        "easy": lambda: arch_cylinder_board("snubhex", 4, 1, 9, cut=21**0.5 / 4),
        "medium": lambda: arch_cylinder_board("snubhex", 5, 2, 27, cut=21**0.5 / 4),
        "hard": lambda: arch_cylinder_board("snubhex", 7, 2, 53, cut=21**0.5 / 4),
    },
    "cyltruncsquare": {
        "easy": lambda: arch_cylinder_board("truncsquare", 9, 3, 7),
        "medium": lambda: arch_cylinder_board("truncsquare", 12, 5, 18),
        "hard": lambda: arch_cylinder_board("truncsquare", 16, 7, 45),
    },
    "cyltrunchex": {
        "easy": lambda: arch_cylinder_board(
            "trunchex", 6, 2, 9, cut=0.5 + ROOT3 / 2),
        "medium": lambda: arch_cylinder_board(
            "trunchex", 8, 3, 22, cut=0.5 + ROOT3 / 2),
        "hard": lambda: arch_cylinder_board(
            "trunchex", 10, 4, 48, cut=0.5 + ROOT3 / 2),
    },
}


def build_board(mode: str, difficulty: str) -> Board | Board3D:
    if mode not in _PRESETS:
        raise ValueError(f"unknown mode {mode!r}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    return _PRESETS[mode][difficulty]()
