from __future__ import annotations

import math
from collections import defaultdict
from typing import Hashable

from minesweeper.boards.core import (
    ROOT3,
    Board3D,
    Cell,
    Vec3,
    _dot,
    _normalize,
    _orient_outward,
    _shared_vertex_adjacency,
    _tangent_order,
    newell_normal,
)


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
