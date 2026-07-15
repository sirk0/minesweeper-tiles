from __future__ import annotations

import math

from minesweeper.boards.core import Board, Cell, ROOT3, _shared_vertex_adjacency




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
