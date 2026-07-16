import math
from collections import Counter, defaultdict

import pytest

from minesweeper.boards import (
    _ARCH_CONFIGS,
    ARCH_TILINGS,
    DIFFICULTIES,
    GROUPS,
    MODE_LABELS,
    MODES_3D,
    SURFACE_LABELS,
    TILINGS,
    arch_mobius_board,
    arch_torus_board,
    archimedean_board,
    build_board,
    c80_board,
    c180_board,
    cube_board,
    cube_frame_board,
    cylinder_board,
    cylinder_hex_board,
    cylinder_triangle_board,
    hat_board,
    hex_board,
    hexhex_board,
    klein_board,
    mobius_board,
    mobius_hex_board,
    mobius_triangle_board,
    newell_normal,
    penrose_board,
    snub_dodecahedron_board,
    sphere_board,
    sphere_triangle_board,
    square_board,
    stepped_bipyramid_board,
    surface_of,
    tetrahedron_board,
    tetrahedron_frame_board,
    torus_board,
    torus_hex_board,
    torus_triangle_board,
    triangle_board,
    triangle_grid_board,
)
from minesweeper.boards import (
    boundary_components as _boundary_components,
)
from minesweeper.boards import (
    corner_fans as _corner_fans,
)
from minesweeper.boards import (
    euler_characteristic as _euler_characteristic,
)

# Template tilings split by symmetry type. Archimedean tilings are
# vertex-transitive (every vertex has the same configuration); their Laves
# duals are face-transitive (every tile congruent) and get a different set
# of invariants. Reflective tilings (a plain mirror, not just a glide or
# pinwheel) additionally give left-right / top-bottom symmetric boards.
_VERTEX_TRANSITIVE = [t.key for t in ARCH_TILINGS if t.vertex_transitive]
_FACE_TRANSITIVE = [t.key for t in ARCH_TILINGS if not t.vertex_transitive]
_REFLECTIVE = {
    t.key for t in ARCH_TILINGS
    if t.template().mirror is not None and not t.template().glide
}


def _tile_signature(polygon):
    """A congruence signature: the multiset of edge lengths and interior
    angles, rounded. Two tiles with equal signatures are congruent up to
    rotation and reflection."""
    n = len(polygon)
    edges = sorted(round(math.dist(polygon[i], polygon[(i + 1) % n]), 4)
                   for i in range(n))
    angles = []
    for i in range(n):
        a, b, c = polygon[i - 1], polygon[i], polygon[(i + 1) % n]
        v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
        angles.append(round(abs(math.atan2(v1[0] * v2[1] - v1[1] * v2[0],
                                            v1[0] * v2[0] + v1[1] * v2[1])), 4))
    return (tuple(edges), tuple(sorted(angles)))

# Every registered mode (easy preset) so the invariant suite below covers
# any tiling or surface the moment it is added to the catalog. A few
# extra-small hand-built boards exercise seam edge cases the easy presets
# are too large to reach.
ALL_BOARDS = [build_board(mode, "easy") for mode in sorted(MODE_LABELS)] + [
    square_board(5, 5, 3),
    torus_board(12, 6, 9),
    mobius_board(20, 4, 10),
    mobius_hex_board(14, 3, 6),
    cylinder_triangle_board(16, 6, 11),
    arch_mobius_board("snubsquare", 13, 2, 10),
    archimedean_board("snubhex", 3, 2, 12),
]


@pytest.mark.parametrize("board", ALL_BOARDS, ids=lambda b: b.mode)
class TestInvariants:
    def test_adjacency_is_symmetric(self, board):
        for cell, neighbors in board.adjacency.items():
            for neighbor in neighbors:
                assert cell in board.adjacency[neighbor]

    def test_no_self_adjacency(self, board):
        for cell, neighbors in board.adjacency.items():
            assert cell not in neighbors

    def test_no_duplicate_neighbors(self, board):
        for neighbors in board.adjacency.values():
            assert len(neighbors) == len(set(neighbors))

    def test_polygons_within_bounds(self, board):
        if board.mode in MODES_3D:
            for polygon in board.polygons.values():
                for point in polygon:
                    assert sum(c * c for c in point) <= board.radius**2 + 1e-9
        else:
            for polygon in board.polygons.values():
                for x, y in polygon:
                    assert -1e-9 <= x <= board.width + 1e-9
                    assert -1e-9 <= y <= board.height + 1e-9

    def test_mine_count_leaves_safe_cells(self, board):
        assert 0 < board.mine_count < len(board.adjacency)


class TestCellCounts:
    def test_square(self):
        assert len(square_board(5, 7, 3).adjacency) == 35

    def test_triangle_has_size_squared_cells(self):
        assert len(triangle_board(6, 4).adjacency) == 36
        assert len(triangle_board(8, 4).adjacency) == 64

    def test_triangle_grid(self):
        assert len(triangle_grid_board(5, 9, 4).adjacency) == 45

    def test_hex(self):
        assert len(hex_board(5, 6, 4).adjacency) == 30

    def test_sphere_has_sixty_pentagons(self):
        assert len(sphere_board(7).adjacency) == 60

    def test_hexhex_is_a_centered_hexagonal_number(self):
        # 3R^2 + 3R + 1 cells
        assert len(hexhex_board(3, 5).adjacency) == 37
        assert len(hexhex_board(5, 12).adjacency) == 91

    def test_c80_is_a_chamfered_dodecahedron(self):
        board = c80_board(5)
        sizes = sorted(len(p) for p in board.polygons.values())
        assert len(board.adjacency) == 42
        assert sizes.count(5) == 12 and sizes.count(6) == 30

    def test_torus(self):
        assert len(torus_board(12, 6, 9).adjacency) == 72

    def test_mobius_and_cylinder(self):
        assert len(mobius_board(20, 4, 10).adjacency) == 80
        assert len(cylinder_board(12, 7, 10).adjacency) == 84

    def test_penrose_cell_counts(self):
        assert len(penrose_board(3, 9).adjacency) == 60
        assert len(penrose_board(4, 25).adjacency) == 160
        assert len(penrose_board(5, 70).adjacency) == 430

    def test_penrose_keep_crops_to_a_denser_square_block(self):
        full = penrose_board(5, 25)
        cropped = penrose_board(5, 25, keep=160)
        assert len(cropped.adjacency) == 160
        assert cropped.width / cropped.height < 1.3  # roughly square
        # the square crop fills its bounding box better than the round wheel
        full_density = len(full.adjacency) / (full.width * full.height)
        crop_density = len(cropped.adjacency) / (cropped.width * cropped.height)
        assert crop_density > full_density

    def test_penrose_thick_outnumber_thin_by_phi(self):
        board = penrose_board(5, 70)
        thin = sum(1 for cell in board.adjacency if cell[0] == 0)
        thick = sum(1 for cell in board.adjacency if cell[0] == 1)
        assert abs(thick / thin - 1.618) < 0.02

    def test_penrose_cells_are_rhombi(self):
        board = penrose_board(3, 9)
        for polygon in board.polygons.values():
            assert len(polygon) == 4
            # opposite sides of a rhombus have equal length
            def side(i):
                (x1, y1), (x2, y2) = polygon[i], polygon[(i + 1) % 4]
                return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            sides = [side(i) for i in range(4)]
            assert max(sides) - min(sides) < 1e-6 * max(sides)

    def test_penrose_vertices_are_exact(self):
        # exact Z[zeta] keys: distinct keys must be geometrically far
        # apart (no floating-point near-duplicates)
        board = penrose_board(3, 9)
        points = {p for polygon in board.polygons.values() for p in polygon}
        points = sorted(points)
        min_gap = min(
            ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            for i, (ax, ay) in enumerate(points)
            for bx, by in points[i + 1:i + 30]
        )
        side = penrose_board(3, 9).width / 5  # rhombus side scale
        assert min_gap > side * 0.1

    def test_c180_is_goldberg_gp30(self):
        board = c180_board(10)
        sizes = sorted(len(p) for p in board.polygons.values())
        assert len(board.adjacency) == 92
        assert sizes.count(5) == 12 and sizes.count(6) == 80

    def test_geodesic_sphere_has_80_triangles(self):
        board = sphere_triangle_board(10)
        assert len(board.adjacency) == 80
        assert all(len(p) == 3 for p in board.polygons.values())

    def test_triangle_and_hex_surface_counts(self):
        assert len(torus_triangle_board(10, 5, 12).adjacency) == 100
        assert len(torus_hex_board(6, 12, 9).adjacency) == 72
        assert len(mobius_triangle_board(14, 4, 13).adjacency) == 112
        assert len(mobius_hex_board(14, 3, 6).adjacency) == 42
        assert len(cylinder_triangle_board(16, 6, 11).adjacency) == 96
        assert len(cylinder_hex_board(12, 6, 9).adjacency) == 72


class TestPolygonShapes:
    def test_vertex_counts(self):
        assert all(len(p) == 4 for p in square_board(3, 3, 1).polygons.values())
        assert all(len(p) == 3 for p in triangle_board(4, 2).polygons.values())
        assert all(len(p) == 3 for p in triangle_grid_board(3, 5, 2).polygons.values())
        assert all(len(p) == 6 for p in hex_board(3, 3, 2).polygons.values())
        assert all(len(p) == 5 for p in sphere_board(7).polygons.values())
        assert all(len(p) == 4 for p in torus_board(8, 5, 4).polygons.values())


class TestHat:
    def test_cell_counts(self):
        # a single H seed inflated N times; keep trims to the count
        assert len(hat_board(1, 5).adjacency) == 25
        assert len(hat_board(2, 28).adjacency) == 169
        assert len(hat_board(2, 10, keep=64).adjacency) == 64
        assert len(hat_board(3, 65, keep=430).adjacency) == 430

    def test_every_cell_is_the_same_tridecagon(self):
        # a monotile: every cell is one congruent 13-sided hat
        board = hat_board(2, 10)
        multisets = set()
        for polygon in board.polygons.values():
            assert len(polygon) == 13
            edges = tuple(sorted(
                round(((polygon[i][0] - polygon[(i + 1) % 13][0]) ** 2
                       + (polygon[i][1] - polygon[(i + 1) % 13][1]) ** 2) ** 0.5, 3)
                for i in range(13)))
            multisets.add(edges)
        assert len(multisets) == 1  # all hats congruent

    def test_reflected_hats_are_a_minority(self):
        # the hat tiling forces in mirror-image hats (label 'H1'), roughly
        # one in seven, but always a strict minority
        board = hat_board(2, 28)
        reflected = sum(1 for cell in board.adjacency if cell[0] == "H1")
        assert 0 < reflected < len(board.adjacency) * 0.2

    def test_vertices_are_exact(self):
        # exact Eisenstein-integer ids: distinct keys are a full lattice
        # unit apart, so there are no floating-point near-duplicates
        board = hat_board(2, 10, keep=48)
        points = sorted({p for polygon in board.polygons.values() for p in polygon})
        min_gap = min(
            ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            for i, (ax, ay) in enumerate(points)
            for bx, by in points[i + 1:i + 30]
        )
        shortest_edge = min(
            ((polygon[i][0] - polygon[(i + 1) % 13][0]) ** 2
             + (polygon[i][1] - polygon[(i + 1) % 13][1]) ** 2) ** 0.5
            for polygon in board.polygons.values() for i in range(13)
        )
        assert min_gap > shortest_edge * 0.5


class TestNeighborCounts:
    def test_square_neighborhood(self):
        board = square_board(5, 5, 3)
        assert len(board.adjacency[(0, 0)]) == 3  # corner
        assert len(board.adjacency[(0, 2)]) == 5  # edge
        assert len(board.adjacency[(2, 2)]) == 8  # interior

    def test_triangle_apex_has_three_neighbors(self):
        board = triangle_board(6, 4)
        assert len(board.adjacency[(0, 0)]) == 3

    def test_triangle_interior_has_twelve_neighbors(self):
        board = triangle_board(8, 4)
        assert max(len(n) for n in board.adjacency.values()) == 12
        # a triangle well inside the figure touches 12 others
        assert len(board.adjacency[(5, 5)]) == 12

    def test_triangle_grid_interior_has_twelve_neighbors(self):
        board = triangle_grid_board(5, 9, 4)
        assert len(board.adjacency[(2, 4)]) == 12

    def test_hex_neighborhood(self):
        board = hex_board(5, 6, 4)
        assert len(board.adjacency[(2, 2)]) == 6  # interior
        assert len(board.adjacency[(0, 0)]) == 2  # corner

    def test_sphere_cells_all_have_seven_neighbors(self):
        board = sphere_board(7)
        assert {len(n) for n in board.adjacency.values()} == {7}

    def test_torus_cells_all_have_eight_neighbors(self):
        # the grid wraps in both directions, so there are no border cells
        board = torus_board(12, 6, 9)
        assert {len(n) for n in board.adjacency.values()} == {8}

    def test_torus_wraps_around(self):
        board = torus_board(12, 6, 9)
        assert (0, 0) in board.adjacency[(11, 5)]

    def test_hexhex_neighbor_counts(self):
        board = hexhex_board(3, 5)
        assert len(board.adjacency[(0, 0)]) == 6  # center
        assert len(board.adjacency[(3, 0)]) == 3  # corner of the big hexagon
        assert len(board.adjacency[(1, -3)]) == 4  # edge of the big hexagon

    def test_mobius_seam_glues_flipped(self):
        # column ring-1 meets column 0 upside down
        board = mobius_board(20, 4, 10)
        assert (0, 3) in board.adjacency[(19, 0)]
        assert (0, 0) in board.adjacency[(19, 3)]

    def test_cylinder_wraps_ring_but_not_ends(self):
        board = cylinder_board(12, 7, 10)
        assert (11, 0) in board.adjacency[(0, 0)]  # wraps around the ring
        assert len(board.adjacency[(3, 3)]) == 8  # interior
        assert len(board.adjacency[(3, 0)]) == 5  # open bottom edge

    def test_hex_torus_is_borderless(self):
        # pure hexagonal tiling: only possible because the torus has
        # Euler characteristic 0
        board = torus_hex_board(6, 12, 9)
        assert {len(n) for n in board.adjacency.values()} == {6}

    def test_triangle_torus_is_borderless(self):
        board = torus_triangle_board(10, 5, 12)
        assert {len(n) for n in board.adjacency.values()} == {12}

    def test_hex_mobius_seam_glues_flipped(self):
        board = mobius_hex_board(14, 3, 6)
        # column ring-1 meets column 0 with rows flipped (row 0 -> row 2)
        assert (0, 0) in board.adjacency[(2, 13)]
        assert (2, 0) in board.adjacency[(0, 13)]

    def test_hex_mobius_requires_odd_rows(self):
        with pytest.raises(ValueError):
            mobius_hex_board(14, 4, 6)

    def test_triangle_cylinder_requires_even_ring(self):
        with pytest.raises(ValueError):
            cylinder_triangle_board(15, 6, 11)

    @pytest.mark.parametrize("mode", ["hex", "trigrid"])
    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_flat_grids_are_roughly_square(self, mode, difficulty):
        board = build_board(mode, difficulty)
        assert 0.85 < board.width / board.height < 1.18

    def test_polygons_face_outward(self):
        for board in (
            sphere_board(7),
            c180_board(10),
            sphere_triangle_board(10),
            cube_board(4, 12),
            tetrahedron_board(8, 4),
            torus_board(12, 6, 9),
            torus_triangle_board(10, 5, 12),
            torus_hex_board(6, 12, 9),
        ):
            for cell, polygon in board.polygons.items():
                normal = newell_normal(polygon)
                centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
                if board.mode in ("sphere", "c180", "spheretri", "cube", "tetrahedron"):
                    outward = centroid
                else:
                    import math

                    ring_scale = math.hypot(centroid[0], centroid[1])
                    outward = (
                        centroid[0] - centroid[0] / ring_scale,
                        centroid[1] - centroid[1] / ring_scale,
                        centroid[2],
                    )
                dot = sum(n * o for n, o in zip(normal, outward))
                assert dot > 0, (board.mode, cell)

    def test_hex_neighbors_match_offset_layout(self):
        board = hex_board(5, 6, 4)
        # odd row (1, 2) is shifted right: neighbors above/below are cols 2-3
        assert set(board.adjacency[(1, 2)]) == {
            (0, 2), (0, 3), (1, 1), (1, 3), (2, 2), (2, 3),
        }


class TestArchimedean:
    """The eight non-regular Archimedean tilings (six with two tile
    shapes, plus 3.4.6.4 and 4.6.12 with three)."""

    @pytest.mark.parametrize("mode", sorted(_VERTEX_TRANSITIVE))
    def test_has_exactly_the_two_configured_shapes(self, mode):
        config, _ = _ARCH_CONFIGS[mode]
        board = archimedean_board(mode, 5, 5, 5)
        assert {len(p) for p in board.polygons.values()} == set(config)

    @pytest.mark.parametrize("mode", sorted(_VERTEX_TRANSITIVE))
    def test_interior_vertex_configuration(self, mode):
        """Around every interior vertex the tile sizes must match the
        tiling's vertex configuration (e.g. 3.3.4.3.4). Vertex-transitive
        (Archimedean) tilings only; Laves duals vary vertex by vertex."""
        config, _ = _ARCH_CONFIGS[mode]
        board = archimedean_board(mode, 5, 5, 5)
        at_vertex = defaultdict(list)
        for polygon in board.polygons.values():
            n = len(polygon)
            for i, point in enumerate(polygon):
                key = (round(point[0], 6), round(point[1], 6))
                before, after = polygon[i - 1], polygon[(i + 1) % n]
                v1 = (before[0] - point[0], before[1] - point[1])
                v2 = (after[0] - point[0], after[1] - point[1])
                angle = abs(
                    math.atan2(
                        v1[0] * v2[1] - v1[1] * v2[0],
                        v1[0] * v2[0] + v1[1] * v2[1],
                    )
                )
                at_vertex[key].append((n, angle))
        interior = 0
        for entries in at_vertex.values():
            if abs(sum(a for _, a in entries) - 2 * math.pi) < 1e-6:
                interior += 1
                assert sorted(s for s, _ in entries) == sorted(config)
        assert interior > 10  # the check actually saw interior vertices

    @pytest.mark.parametrize("mode", sorted(_FACE_TRANSITIVE))
    def test_tiles_are_congruent(self, mode):
        """A face-transitive (Laves) tiling is built from one congruent
        tile: every polygon has the same sorted edge lengths and interior
        angles (up to rotation/reflection). Empty until Laves tilings land;
        it then covers each automatically."""
        board = archimedean_board(mode, 5, 5, 5)
        signatures = {_tile_signature(p) for p in board.polygons.values()}
        assert len(signatures) == 1, f"{mode} has non-congruent tiles"

    @pytest.mark.parametrize("mode", sorted(_ARCH_CONFIGS))
    def test_no_overlapping_tiles(self, mode):
        # any edge shared by more than two tiles means overlap
        board = archimedean_board(mode, 5, 5, 5)
        edge_count = defaultdict(int)
        for polygon in board.polygons.values():
            n = len(polygon)
            for i in range(n):
                a = (round(polygon[i][0], 6), round(polygon[i][1], 6))
                b = (round(polygon[(i + 1) % n][0], 6), round(polygon[(i + 1) % n][1], 6))
                edge_count[frozenset((a, b))] += 1
        assert all(count <= 2 for count in edge_count.values())

    # the reflective tilings (cmm / p4m / p6m) get a plain mirror; the
    # chiral/glide tilings (p4g glide, p6) can only manage the pinwheel
    # rotation. Derived so a new tiling classifies itself.
    REFLECTIVE = _REFLECTIVE

    @staticmethod
    def _symmetry(board, reflect):
        """The largest fraction of tiles that map onto another tile when
        the board is reflected/rotated about a centre. A symmetry centre
        sits at a largest-tile centroid (vertex-transitive tilings) or at
        a vertex (some face-transitive Laves tilings), so scan both sets of
        candidates and take the best."""
        polygons = list(board.polygons.values())
        centroids = [(sum(x for x, _ in p) / len(p),
                      sum(y for _, y in p) / len(p)) for p in polygons]
        biggest = max(len(p) for p in polygons)
        tol = 0.2 * min(math.dist(p[i], p[(i + 1) % len(p)])
                        for p in polygons for i in range(len(p)))
        grid = defaultdict(list)
        for x, y in centroids:
            grid[(round(x / tol), round(y / tol))].append((x, y))

        def present(rx, ry):
            gx, gy = round(rx / tol), round(ry / tol)
            return any(abs(px - rx) < tol and abs(py - ry) < tol
                       for i in (-1, 0, 1) for j in (-1, 0, 1)
                       for px, py in grid.get((gx + i, gy + j), ()))

        board_cx = sum(x for x, _ in centroids) / len(centroids)
        board_cy = sum(y for _, y in centroids) / len(centroids)
        vertices = {(round(x, 6), round(y, 6))
                    for p in polygons for x, y in p}
        # candidate centres near the middle: biggest-tile centroids and
        # vertices (a rotation centre lies on one of them)
        candidates = [c for p, c in zip(polygons, centroids)
                      if len(p) == biggest]
        candidates += sorted(vertices, key=lambda v: (v[0] - board_cx) ** 2
                             + (v[1] - board_cy) ** 2)[:12]
        best = 0.0
        for cx, cy in candidates:
            hits = sum(1 for x, y in centroids if present(*reflect(cx, cy, x, y)))
            best = max(best, hits / len(centroids))
        return best

    @pytest.mark.parametrize("mode", sorted(_ARCH_CONFIGS))
    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_flat_board_is_symmetric(self, mode, difficulty):
        """A symmetric tiling must give a symmetric board: no stray tiles
        poking out one side."""
        board = build_board(mode, difficulty)
        # a rectangular window on a hexagonal tiling can leave a few edge
        # tiles unpaired, so the bar is well clear of a ragged disc (which
        # scores ~0.3) rather than a perfect 1.0
        rotation = self._symmetry(board, lambda cx, cy, x, y: (2 * cx - x, 2 * cy - y))
        assert rotation >= 0.85
        if mode in self.REFLECTIVE:
            lr = self._symmetry(board, lambda cx, cy, x, y: (2 * cx - x, y))
            tb = self._symmetry(board, lambda cx, cy, x, y: (x, 2 * cy - y))
            assert max(lr, tb) >= 0.9

    def test_snub_dodecahedron_is_12_pentagons_80_triangles(self):
        board = snub_dodecahedron_board(10)
        sizes = sorted(len(p) for p in board.polygons.values())
        assert len(board.adjacency) == 92
        assert sizes.count(3) == 80 and sizes.count(5) == 12


class TestCubeFrame:
    """The cube-frame (level-1 Menger sponge) surface: a genus-5 polycube
    boundary tiled by unit squares."""

    def test_all_cells_are_quads(self):
        board = cube_frame_board(6, 2, 40)
        assert all(len(p) == 4 for p in board.polygons.values())

    def test_hole_removes_the_face_centers(self):
        # a plain 6x6x6 cube surface would have 6*36 = 216 squares; boring a
        # 2x2 hole through each face and hollowing the middle leaves the
        # twelve edge bars, whose surface is 288 squares
        assert len(cube_frame_board(6, 2, 40).adjacency) == 288

    @pytest.mark.parametrize(
        "n, thickness, genus", [(6, 2, 5), (9, 3, 5), (12, 4, 5)]
    )
    def test_surface_is_genus_five(self, n, thickness, genus):
        # a cube frame is topologically a cube with a tunnel through each
        # pair of opposite faces: chi = 2 - 2*genus = -8
        board = cube_frame_board(n, thickness, 10)
        vertices = len(_corner_fans(board))
        edges = set()
        for polygon in board.polygons.values():
            points = [tuple(round(c, 6) for c in v) for v in polygon]
            for a, b in zip(points, points[1:] + points[:1]):
                edges.add(frozenset((a, b)))
        chi = vertices - len(edges) + len(board.polygons)
        assert chi == 2 - 2 * genus

    def test_surface_is_closed(self):
        # every edge borders exactly two faces: no boundary, so back-face
        # culling (not two_sided rendering) is correct
        board = cube_frame_board(6, 2, 40)
        assert _boundary_components(board) == 0
        assert board.two_sided is False

    def test_orientation_is_consistent_and_outward(self):
        # a consistently wound closed mesh traverses every shared edge once
        # in each direction; check that, then pin the global sign outward
        # via an outer +x face (all its corners sit at x = +1)
        board = cube_frame_board(6, 2, 40)
        directed = [
            (tuple(round(c, 6) for c in a), tuple(round(c, 6) for c in b))
            for polygon in board.polygons.values()
            for a, b in zip(polygon, polygon[1:] + polygon[:1])
        ]
        assert len(directed) == len(set(directed))  # no edge repeated a way
        outer = next(
            p for p in board.polygons.values() if all(v[0] > 0.99 for v in p)
        )
        assert newell_normal(outer)[0] > 0  # normal points along +x, outward

    def test_thickness_must_leave_a_hole(self):
        with pytest.raises(ValueError):
            cube_frame_board(4, 2, 5)  # 2*2 == 4: no hole left


class TestTetrahedronFrame:
    """The tetrahedron frame (level-1 Sierpiński tetrahedron): four
    half-scale corner tetrahedra meeting only at the six edge-midpoints of
    the original, tiled with flat triangles."""

    @pytest.mark.parametrize("frequency", [2, 3, 4])
    def test_cell_count_is_sixteen_faces_of_triangles(self, frequency):
        board = tetrahedron_frame_board(5, frequency)
        # 4 corner tetrahedra * 4 faces * frequency**2 triangles
        assert len(board.polygons) == 16 * frequency * frequency
        assert all(len(p) == 3 for p in board.polygons.values())

    def test_surface_is_closed(self):
        # each corner tetrahedron is a closed manifold; every edge borders two
        # faces, so back-face culling (not two_sided rendering) is correct
        board = tetrahedron_frame_board(5, 3)
        assert _boundary_components(board) == 0
        assert board.two_sided is False

    def test_graph_is_connected_through_the_pinch_points(self):
        # the four corner tetrahedra touch only at shared edge-midpoints, but
        # vertex-adjacency there still links them into one component
        board = tetrahedron_frame_board(5, 3)
        seen, stack = set(), [next(iter(board.adjacency))]
        while stack:
            cell = stack.pop()
            if cell not in seen:
                seen.add(cell)
                stack.extend(board.adjacency[cell])
        assert len(seen) == len(board.adjacency)

    def test_orientation_is_outward_at_an_original_corner(self):
        # the three faces meeting at an original corner (e.g. (1, 1, 1)) sit on
        # the outer hull, so their normals point away from the origin there
        board = tetrahedron_frame_board(5, 2)
        corner = (1.0, 1.0, 1.0)
        outer = [
            p for p in board.polygons.values()
            if any(tuple(round(c, 6) for c in v) == corner for v in p)
        ]
        assert outer
        for polygon in outer:
            centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
            assert sum(n * c for n, c in zip(newell_normal(polygon), centroid)) > 0


class TestSteppedCube:
    """The stepped-cube board: a stepped pyramid stitched base-to-base
    with its z-mirror, forming a terraced bipyramid (a sphere)."""

    def test_all_cells_are_quads(self):
        board = stepped_bipyramid_board(6, 3, 20)
        assert all(len(p) == 4 for p in board.polygons.values())

    def test_easy_cell_count(self):
        assert len(stepped_bipyramid_board(6, 3, 20).adjacency) == 144

    @pytest.mark.parametrize("base, levels", [(6, 3), (8, 4), (10, 5)])
    def test_surface_is_a_sphere(self, base, levels):
        # a solid terraced diamond is a topological sphere: chi = 2
        board = stepped_bipyramid_board(base, levels, 10)
        vertices = len(_corner_fans(board))
        edges = set()
        for polygon in board.polygons.values():
            points = [tuple(round(c, 6) for c in v) for v in polygon]
            for a, b in zip(points, points[1:] + points[:1]):
                edges.add(frozenset((a, b)))
        assert vertices - len(edges) + len(board.polygons) == 2

    def test_surface_is_closed_and_outward(self):
        board = stepped_bipyramid_board(8, 4, 40)
        assert _boundary_components(board) == 0
        assert board.two_sided is False
        directed = [
            (tuple(round(c, 6) for c in a), tuple(round(c, 6) for c in b))
            for polygon in board.polygons.values()
            for a, b in zip(polygon, polygon[1:] + polygon[:1])
        ]
        assert len(directed) == len(set(directed))  # consistently wound
        # the very top cap is a square facing straight up (+z)
        top = max(v[2] for p in board.polygons.values() for v in p)
        cap = next(
            p for p in board.polygons.values()
            if all(abs(v[2] - top) < 1e-6 for v in p)
        )
        assert newell_normal(cap)[2] > 0

    def test_widest_terrace_is_the_equator(self):
        # the middle layer spans the full base; the two poles are smaller,
        # so the widest cross-section sits at z = 0 (mirror symmetry)
        board = stepped_bipyramid_board(8, 4, 40)
        zs = [v[2] for p in board.polygons.values() for v in p]
        assert abs(min(zs) + max(zs)) < 1e-6  # symmetric about z = 0

    def test_needs_two_levels_and_a_positive_apex(self):
        with pytest.raises(ValueError):
            stepped_bipyramid_board(6, 1, 5)  # a single level is just a slab
        with pytest.raises(ValueError):
            stepped_bipyramid_board(4, 3, 5)  # apex 4 - 2*2 = 0: nothing left




class TestKleinBottle:
    """The Klein bottle: the square grid on the classic self-intersecting
    bottle immersion -- closed (no boundary) but non-orientable, and
    carrying a ring-translation ``cell_cycle`` for scroll-to-shift."""

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_is_a_closed_non_orientable_surface(self, difficulty):
        board = build_board("klein", difficulty)
        assert _euler_characteristic(board) == 0
        assert _boundary_components(board) == 0
        assert board.two_sided is True  # non-orientable: drawn both sides
        assert {len(n) for n in board.adjacency.values()} == {8}

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_immersion_keeps_every_vertex_distinct(self, difficulty):
        # a closed quad mesh with chi = 0 has V = F; if the immersion merged
        # two grid vertices the distinct-point count would drop below F
        board = build_board("klein", difficulty)
        points = {tuple(round(c, 6) for c in p)
                  for poly in board.polygons.values() for p in poly}
        assert len(points) == len(board.polygons)

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_cell_cycle_is_a_graph_automorphism(self, difficulty):
        board = build_board("klein", difficulty)
        cycle = board.cell_cycle
        assert cycle is not None
        # a bijection over exactly the cells
        assert set(cycle) == set(board.adjacency)
        assert len(set(cycle.values())) == len(cycle)
        # adjacency-preserving: neighbours map to neighbours (so the board
        # reads correctly at every scroll offset)
        for cell, neighbors in board.adjacency.items():
            shifted = board.adjacency[cycle[cell]]
            assert all(cycle[n] in shifted for n in neighbors)

    def test_cell_cycle_period_is_twice_the_ring(self):
        # crossing the seam flips the tube, so a cell returns to itself only
        # after two full loops: order 2 * ring (here ring = 12)
        board = klein_board(12, 6, 9)
        cycle = board.cell_cycle
        start = next(iter(cycle))
        cur, order = cycle[start], 1
        while cur != start:
            cur, order = cycle[cur], order + 1
        assert order == 24

    def test_tube_must_be_even(self):
        # the seam reflection j -> tube/2 - j - 1 only lands on cells when
        # tube is even
        with pytest.raises(ValueError):
            klein_board(12, 5, 9)


class TestWrappedArchimedean:
    """The Archimedean tilings wrapped onto the donut, cylinder and
    Möbius strip."""

    WRAPPED = [
        mode
        for mode in MODE_LABELS
        if mode.startswith(("torus", "mobius", "cyl"))
        and any(mode.endswith(tiling) for tiling in _ARCH_CONFIGS)
    ]

    # only the vertex-transitive (Archimedean) tilings have a single vertex
    # configuration to check; Laves duals vary vertex by vertex.
    WRAPPED_VERTEX_TRANSITIVE = [
        m for m in WRAPPED if any(m.endswith(t) for t in _VERTEX_TRANSITIVE)
    ]

    @pytest.mark.parametrize("tiling", sorted(_VERTEX_TRANSITIVE))
    def test_torus_vertex_configuration_everywhere(self, tiling):
        """A torus has no boundary, so every single vertex must show the
        tiling's full vertex configuration."""
        board = build_board("torus" + tiling, "easy")
        config = sorted(_ARCH_CONFIGS[tiling][0])
        for fan in _corner_fans(board).values():
            assert sorted(fan) == config

    @pytest.mark.parametrize("mode", sorted(WRAPPED_VERTEX_TRANSITIVE))
    def test_vertices_are_full_or_boundary(self, mode):
        """On the open surfaces every vertex fan is the configuration or
        a part of it (boundary vertices)."""
        board = build_board(mode, "easy")
        tiling = next(t for t in _ARCH_CONFIGS if mode.endswith(t))
        want = Counter(_ARCH_CONFIGS[tiling][0])
        for fan in _corner_fans(board).values():
            assert not Counter(fan) - want, (mode, fan)

    @pytest.mark.parametrize("mode", sorted(WRAPPED))
    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_euler_characteristic_is_zero(self, mode, difficulty):
        # the torus, cylinder and Möbius strip all have chi = 0
        board = build_board(mode, difficulty)
        vertices = len(_corner_fans(board))
        edges = set()
        for polygon in board.polygons.values():
            points = [tuple(round(c, 6) for c in p) for p in polygon]
            for a, b in zip(points, points[1:] + points[:1]):
                edges.add(frozenset((a, b)))
        assert vertices - len(edges) + len(board.polygons) == 0

    @pytest.mark.parametrize("mode", sorted(WRAPPED))
    def test_boundary_circles_match_the_surface(self, mode):
        """The seam gluing is what distinguishes the surfaces: a torus is
        closed, a cylinder has two rims, a Möbius strip has one. Each
        surface's expected count is declared once on its SurfaceSpec."""
        board = build_board(mode, "easy")
        assert _boundary_components(board) == surface_of(mode).boundary_components

    def test_cell_counts(self):
        counts = {
            "toruselongated": (72, 168, 240),
            "torussnubsquare": (60, 126, 240),
            "toruskagome": (96, 120, 216),
            "torussnubhex": (72, 108, 252),
            "torustruncsquare": (72, 144, 224),
            "torustrunchex": (84, 120, 216),
            "cylelongated": (70, 156, 285),
            "cylsnubsquare": (60, 126, 270),
            "cylkagome": (72, 162, 264),
            "cylsnubhex": (72, 180, 252),
            "cyltruncsquare": (54, 120, 224),
            "cyltrunchex": (72, 144, 240),
            "mobiuselongated": (72, 144, 216),
            "mobiussnubsquare": (78, 135, 204),
            "mobiuskagome": (72, 144, 216),
            "mobiustruncsquare": (72, 128, 220),
            "mobiustrunchex": (54, 120, 216),
            "torusrhombitrihex": (120, 168, 288),
            "torustrunctrihex": (120, 168, 288),
            "cylrhombitrihex": (96, 180, 252),
            "cyltrunctrihex": (96, 180, 252),
            "mobiusrhombitrihex": (96, 144, 288),
            "mobiustrunctrihex": (96, 144, 288),
        }
        assert sorted(counts) == sorted(self.WRAPPED)
        for mode, expected in counts.items():
            for difficulty, count in zip(DIFFICULTIES, expected):
                assert len(build_board(mode, difficulty).adjacency) == count

    def test_snubhex_is_chiral_so_no_mobius(self):
        # 3.3.3.3.6 has no mirror or glide symmetry: its mirror image is
        # a different (opposite-handed) tiling, so no Möbius gluing
        assert "mobiussnubhex" not in MODE_LABELS
        with pytest.raises(ValueError):
            arch_mobius_board("snubhex", 8, 1, 5)

    def test_snubsquare_mobius_needs_odd_half_domains(self):
        # p4g glues via a glide (mirror + half a period): a whole number
        # of periods would need a plain mirror, which p4g lacks
        with pytest.raises(ValueError):
            arch_mobius_board("snubsquare", 12, 2, 10)

    def test_too_small_wraps_rejected(self):
        with pytest.raises(ValueError):
            arch_torus_board("kagome", 1, 3, 2)

    def test_torus_polygons_face_outward(self):
        for tiling in sorted(_ARCH_CONFIGS):
            board = build_board("torus" + tiling, "easy")
            for cell, polygon in board.polygons.items():
                normal = newell_normal(polygon)
                centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
                ring_scale = math.hypot(centroid[0], centroid[1])
                outward = (
                    centroid[0] - centroid[0] / ring_scale,
                    centroid[1] - centroid[1] / ring_scale,
                    centroid[2],
                )
                assert sum(n * o for n, o in zip(normal, outward)) > 0, (
                    board.mode,
                    cell,
                )


class TestPolyhedra:
    """The cube and the tetrahedron: closed, convex, flat-faced solids
    (sphere topology, so Euler characteristic 2)."""

    @pytest.mark.parametrize("n", [2, 4, 6])
    def test_cube_is_six_square_faces(self, n):
        board = cube_board(n, 5)
        assert len(board.polygons) == 6 * n * n
        assert all(len(p) == 4 for p in board.polygons.values())

    @pytest.mark.parametrize("frequency", [1, 4, 6])
    def test_tetrahedron_is_four_triangular_faces(self, frequency):
        board = tetrahedron_board(3, frequency)
        assert len(board.polygons) == 4 * frequency * frequency
        assert all(len(p) == 3 for p in board.polygons.values())

    @pytest.mark.parametrize(
        "board", [cube_board(5, 5), tetrahedron_board(3, 5)], ids=lambda b: b.mode
    )
    def test_closed_surface_no_boundary(self, board):
        assert _boundary_components(board) == 0

    @pytest.mark.parametrize(
        "board", [cube_board(5, 5), tetrahedron_board(3, 5)], ids=lambda b: b.mode
    )
    def test_euler_characteristic_is_two(self, board):
        assert _euler_characteristic(board) == 2

    @pytest.mark.parametrize(
        "board", [cube_board(4, 5), tetrahedron_board(3, 4)], ids=lambda b: b.mode
    )
    def test_faces_stitch_into_one_connected_surface(self, board):
        # shared edge/corner vertices must join every face; a flood must
        # reach all cells (a face left unstitched splits the graph)
        adjacency = board.adjacency
        start = next(iter(adjacency))
        seen, stack = {start}, [start]
        while stack:
            for neighbor in adjacency[stack.pop()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        assert len(seen) == len(adjacency)


class TestPresets:
    @pytest.mark.parametrize("mode", sorted(MODE_LABELS))
    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_all_presets_build(self, mode, difficulty):
        board = build_board(mode, difficulty)
        assert board.mode == mode
        if mode in MODES_3D:
            assert board.radius > 0
        else:
            assert board.width > 0 and board.height > 0
        assert 0 < board.mine_count < len(board.adjacency)

    def test_unknown_mode_and_difficulty_rejected(self):
        with pytest.raises(ValueError):
            build_board("nope", "easy")
        with pytest.raises(ValueError):
            build_board("square", "nope")

    def test_every_mode_appears_exactly_once_in_the_menu(self):
        modes = [m for _, modes in GROUPS.values() for m in modes]
        modes += [m for _, surfaces in TILINGS.values() for m in surfaces.values()]
        assert sorted(modes) == sorted(MODE_LABELS)
        assert len(modes) == len(set(modes))

    def test_tilings_use_known_surfaces(self):
        for _, surfaces in TILINGS.values():
            assert set(surfaces) <= set(SURFACE_LABELS)
