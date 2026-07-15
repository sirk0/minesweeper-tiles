from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from minesweeper.boards.core import Board, LatticePoint, ROOT3, _HEX_VERTEX_OFFSETS, _build, _finalize_flat




# -- 2D builders (cells keyed by (row, index)) ------------------------------
#
# AGENT NOTE (convention for all future flat boards): a finite flat board
# must read as a roughly *square* rectangle, never a round disc, and if
# the tiling is symmetric the board should be too (matching edges, no lone
# tiles poking out on one side). How to get there depends on the tiling:
#   * Periodic tilings -- take a rectangular window of whole periods
#     centred on a rotation centre of the tiling, so the window maps onto
#     itself under the tiling's point group (mirror for the reflective
#     tilings, pinwheel rotation for the chiral ones). archimedean_board
#     does this from the _ArchTemplate domains; square/hex/triangle boards
#     are naturally rectangular.
#   * Aperiodic tilings (Penrose, Hat) have no period to repeat, so grow a
#     generous patch and trim to the ``keep`` centremost cells by
#     Chebyshev distance ``max(|dx|, |dy|)`` from the centroid, which
#     carves out a square. See penrose_board and hat_board.
# Never bound a player-facing board by Euclidean ``dx^2 + dy^2 <= r^2``:
# that leaves a circle.


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


# -- Archimedean (semiregular) tilings ---------------------------------------
#
# Each of the eight non-regular uniform tilings, as (vertex
# configuration, number of distinct edge directions) -- e.g. snub square
# is 3.3.4.3.4 with edges every 30 degrees (12 directions). Six have two
# tile shapes; the last two (3.4.6.4 and 4.6.12) have three. Every flat
# and 3D Archimedean board is assembled from one rectangular periodic
# domain (the ``_ArchTemplate`` builders far below); this table is the
# shape catalogue the tests validate the built tilings against.

_ARCH_CONFIGS = {
    "elongated": ((3, 3, 3, 4, 4), 12),
    "snubsquare": ((3, 3, 4, 3, 4), 12),
    "kagome": ((3, 6, 3, 6), 12),
    "snubhex": ((3, 3, 3, 3, 6), 12),
    "truncsquare": ((4, 8, 8), 8),
    "trunchex": ((3, 12, 12), 12),
    "rhombitrihex": ((3, 4, 6, 4), 12),
    "trunctrihex": ((4, 6, 12), 12),
}


# -- Archimedean tilings on wrapped surfaces ---------------------------------
#
# Each Archimedean tiling is reduced to one rectangular fundamental domain
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
    orthogonal superlattice vectors (5,1) and (3,-5) (in half-side /
    row-height units of the underlying triangular lattice): sqrt(7) x
    sqrt(21) edge lengths holding two hexagons and sixteen triangles, with
    hexagon centres on the sqrt(7) superlattice. The tiling is chiral
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


def _hex_lattice_polygons(centre_at, hexagon_at, decorate, width, height):
    """Assemble one rectangular domain of a tiling built on a triangular
    lattice of hexagon (or dodecagon) centres. ``hexagon_at(cx, cy)`` is
    the central polygon around a lattice point and ``decorate(cx, cy)``
    yields the polygons hung off it (shared with neighbours); everything
    is deduplicated by rounded centroid and kept when its centroid lands
    in [0, width) x [0, height)."""
    def centroid(polygon):
        return (sum(x for x, _ in polygon) / len(polygon),
                sum(y for _, y in polygon) / len(polygon))

    polygons = {}
    for m in range(-2, 4):
        for n in range(-2, 4):
            cx, cy = centre_at(m, n)
            for name, polygon in [("c", hexagon_at(cx, cy)), *decorate(cx, cy)]:
                gx, gy = centroid(polygon)
                if -1e-9 <= gx < width - 1e-9 and -1e-9 <= gy < height - 1e-9:
                    polygons[(name, round(gx, 3), round(gy, 3))] = polygon
    return [(f"{name}{i}", polygon)
            for i, ((name, _, _), polygon) in enumerate(polygons.items())]


def _regular_polygon(cx, cy, sides, circumradius, offset_deg):
    return [(cx + circumradius * math.cos(math.radians(offset_deg + 360 * k / sides)),
             cy + circumradius * math.sin(math.radians(offset_deg + 360 * k / sides)))
            for k in range(sides)]


def _square_on_edge(cx, cy, apothem, normal_deg):
    """The unit square sitting outside the edge whose outward normal is
    ``normal_deg`` at distance ``apothem`` from (cx, cy)."""
    phi = math.radians(normal_deg)
    ux, uy = math.cos(phi), math.sin(phi)
    tx, ty = -uy, ux  # along the edge
    mx, my = cx + apothem * ux, cy + apothem * uy
    a = (mx + 0.5 * tx, my + 0.5 * ty)
    b = (mx - 0.5 * tx, my - 0.5 * ty)
    return [a, b, (b[0] + ux, b[1] + uy), (a[0] + ux, a[1] + uy)]


def _rhombitrihex_template() -> _ArchTemplate:
    """Rhombitrihexagonal (3.4.6.4): hexagons on a triangular lattice of
    pitch 1+sqrt(3), a square shared across every hexagon edge and a
    triangle in every gap between two squares. The rectangle holds two
    hexagons, six squares and four triangles."""
    a = 1 + ROOT3

    def centre_at(m, n):
        return (m * a + n * a / 2, n * a * ROOT3 / 2)

    def hexagon_at(cx, cy):
        return _regular_polygon(cx, cy, 6, 1.0, 30)  # vertices at 30, 90, ...

    def decorate(cx, cy):
        out = []
        for k in range(6):
            out.append(("sq", _square_on_edge(cx, cy, ROOT3 / 2, 60 * k)))
            vx = cx + math.cos(math.radians(30 + 60 * k))
            vy = cy + math.sin(math.radians(30 + 60 * k))
            u1 = (math.cos(math.radians(60 * k)), math.sin(math.radians(60 * k)))
            u2 = (math.cos(math.radians(60 * k + 60)), math.sin(math.radians(60 * k + 60)))
            out.append(("tri", [(vx, vy), (vx + u1[0], vy + u1[1]),
                                (vx + u2[0], vy + u2[1])]))
        return out

    width, height = a, a * ROOT3
    polygons = _hex_lattice_polygons(centre_at, hexagon_at, decorate, width, height)
    return _template((3, 4, 6, 4), width, height, polygons)


def _trunctrihex_template() -> _ArchTemplate:
    """Truncated trihexagonal (4.6.12): dodecagons on a triangular lattice
    of pitch 3+sqrt(3), a square shared across every second dodecagon edge
    (facing a neighbour) and a hexagon in each triangular gap between three
    dodecagons. The rectangle holds two dodecagons, six squares and four
    hexagons."""
    a = 3 + ROOT3
    r12 = (6**0.5 + 2**0.5) / 2  # dodecagon circumradius, side 1
    apothem = (2 + ROOT3) / 2

    def centre_at(m, n):
        return (m * a + n * a / 2, n * a * ROOT3 / 2)

    def dodecagon_at(cx, cy):
        return _regular_polygon(cx, cy, 12, r12, 15)

    def decorate(cx, cy):
        # this dodecagon's lattice indices, to locate its triangular holes
        n0 = round(cy / (a * ROOT3 / 2))
        m0 = round((cx - n0 * a / 2) / a)
        out = [("sq", _square_on_edge(cx, cy, apothem, 60 * k)) for k in range(6)]
        for corners in [((0, 0), (1, 0), (0, 1)), ((1, 0), (0, 1), (1, 1))]:
            centres = [centre_at(m0 + dm, n0 + dn) for dm, dn in corners]
            hx = sum(p[0] for p in centres) / 3
            hy = sum(p[1] for p in centres) / 3
            out.append(("hex", _regular_polygon(hx, hy, 6, 1.0, 0)))
        return out

    width, height = a, a * ROOT3
    polygons = _hex_lattice_polygons(centre_at, dodecagon_at, decorate, width, height)
    return _template((4, 6, 12), width, height, polygons)


_ARCH_TEMPLATES = {
    "elongated": _elongated_template,
    "snubsquare": _snubsquare_template,
    "kagome": _kagome_template,
    "snubhex": _snubhex_template,
    "truncsquare": _truncsquare_template,
    "trunchex": _trunchex_template,
    "rhombitrihex": _rhombitrihex_template,
    "trunctrihex": _trunctrihex_template,
}


@lru_cache(maxsize=None)
def _arch_template(tiling: str) -> _ArchTemplate:
    return _ARCH_TEMPLATES[tiling]()


def archimedean_board(
    tiling: str, nx: int, ny: int, mine_count: int, scale: float = 40
) -> Board:
    """A flat, roughly ``nx`` by ``ny`` domain rectangle of an
    Archimedean tiling, built from the tiling's periodic domain (the same
    ``_ArchTemplate`` that wraps the donut/cylinder/Mobius).

    The tiles are kept by centroid inside an ``nx*width`` by ``ny*height``
    window centred on the larger tile nearest the middle -- a square,
    hexagon, octagon or dodecagon, whose centre is always a rotation
    centre of the tiling. Rotating that window 180 degrees maps it (and
    the tiling) onto itself, so the patch is symmetric under the tiling's
    point group: a plain left-right / top-bottom mirror for the reflective
    tilings (that same centre lies on their mirror axes), and the natural
    pinwheel rotation for the chiral snub tilings. That is what keeps the
    edges clean and balanced instead of leaving stray tiles on one side."""
    template = _arch_template(tiling)
    width_units, height_units = template.width, template.height

    def position(key):
        m, n, tag = key
        vx, vy = template.verts[tag]
        return (m * width_units + vx, n * height_units + vy)

    # grow two extra domains all round so the centred window is fully
    # populated, including the outer tiles' shared neighbours
    grown = {
        (m, n, name): [(m + dm, n + dn, tag) for tag, dm, dn in refs]
        for m in range(nx + 2)
        for n in range(ny + 2)
        for name, refs in template.cells
    }
    centroid = {
        cell: (lambda pts: (sum(x for x, _ in pts) / len(pts),
                            sum(y for _, y in pts) / len(pts)))(
            [position(k) for k in keys])
        for cell, keys in grown.items()
    }
    biggest = max(len(keys) for keys in grown.values())
    mid_x, mid_y = (nx + 2) * width_units / 2, (ny + 2) * height_units / 2
    cx, cy = min(
        (c for cell, c in centroid.items() if len(grown[cell]) == biggest),
        key=lambda c: (c[0] - mid_x) ** 2 + (c[1] - mid_y) ** 2,
    )
    half_w, half_h = nx * width_units / 2, ny * height_units / 2
    cells = {
        cell: keys
        for cell, keys in grown.items()
        if abs(centroid[cell][0] - cx) <= half_w + 1e-9
        and abs(centroid[cell][1] - cy) <= half_h + 1e-9
    }

    return _finalize_flat(tiling, cells, position, mine_count, scale)
