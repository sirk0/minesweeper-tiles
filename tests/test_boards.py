import pytest

import math
from collections import Counter, defaultdict

from minesweeper.boards import (
    _ARCH_CONFIGS,
    DIFFICULTIES,
    GROUPS,
    MODE_LABELS,
    MODES_3D,
    SURFACE_LABELS,
    TILINGS,
    arch_cylinder_board,
    arch_mobius_board,
    arch_torus_board,
    archimedean_board,
    build_board,
    snub_dodecahedron_board,
    c80_board,
    c180_board,
    cylinder_board,
    cylinder_hex_board,
    cylinder_triangle_board,
    hex_board,
    hexhex_board,
    mobius_board,
    mobius_hex_board,
    mobius_triangle_board,
    multi_torus_board,
    newell_normal,
    penrose_board,
    sphere_board,
    sphere_triangle_board,
    square_board,
    torus_board,
    torus_hex_board,
    torus_triangle_board,
    triangle_board,
    triangle_grid_board,
)

ALL_BOARDS = [
    square_board(5, 5, 3),
    triangle_board(6, 4),
    triangle_grid_board(5, 9, 4),
    hex_board(5, 6, 4),
    hexhex_board(3, 5),
    penrose_board(3, 9),
    sphere_board(7),
    c80_board(5),
    c180_board(10),
    sphere_triangle_board(10),
    torus_board(12, 6, 9),
    torus_triangle_board(10, 5, 12),
    torus_hex_board(6, 12, 9),
    mobius_board(20, 4, 10),
    mobius_triangle_board(14, 4, 13),
    mobius_hex_board(14, 3, 6),
    cylinder_board(12, 7, 10),
    cylinder_triangle_board(16, 6, 11),
    cylinder_hex_board(12, 6, 9),
    snub_dodecahedron_board(10),
    archimedean_board("elongated", 4, 11),
    archimedean_board("snubsquare", 4, 11),
    archimedean_board("kagome", 5.5, 11),
    archimedean_board("snubhex", 4.2, 12),
    archimedean_board("truncsquare", 8, 10),
    archimedean_board("trunchex", 11, 13),
    arch_torus_board("elongated", 12, 1, 9),
    arch_torus_board("snubsquare", 5, 2, 8),
    arch_torus_board("kagome", 8, 2, 12),
    arch_torus_board("snubhex", 4, 1, 9),
    arch_torus_board("truncsquare", 9, 4, 9),
    arch_torus_board("trunchex", 7, 2, 10),
    arch_cylinder_board("elongated", 10, 1, 8),
    arch_cylinder_board("snubsquare", 5, 2, 8),
    arch_cylinder_board("kagome", 6, 2, 9),
    arch_cylinder_board("snubhex", 4, 1, 9),
    arch_cylinder_board("truncsquare", 9, 3, 7),
    arch_cylinder_board("trunchex", 6, 2, 9),
    arch_mobius_board("elongated", 12, 1, 9),
    arch_mobius_board("snubsquare", 13, 2, 10),
    arch_mobius_board("kagome", 12, 1, 9),
    arch_mobius_board("truncsquare", 12, 3, 9),
    arch_mobius_board("trunchex", 9, 1, 7),
    multi_torus_board("square", 2, 9, 5, 10),
    multi_torus_board("tri", 3, 6, 4, 15),
    multi_torus_board("hex", 2, 8, 6, 12),
    multi_torus_board("kagome", 3, 3, 2, 14),
    multi_torus_board("snubhex", 2, 3, 1, 13),
    multi_torus_board("truncsquare", 3, 5, 3, 12),
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
            torus_board(12, 6, 9),
            torus_triangle_board(10, 5, 12),
            torus_hex_board(6, 12, 9),
        ):
            for cell, polygon in board.polygons.items():
                normal = newell_normal(polygon)
                centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
                if board.mode in ("sphere", "c180", "spheretri"):
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
    """The six semiregular tilings with two tile shapes."""

    @pytest.mark.parametrize("mode", sorted(_ARCH_CONFIGS))
    def test_has_exactly_the_two_configured_shapes(self, mode):
        config, _ = _ARCH_CONFIGS[mode]
        board = archimedean_board(mode, 6, 5)
        assert {len(p) for p in board.polygons.values()} == set(config)

    @pytest.mark.parametrize("mode", sorted(_ARCH_CONFIGS))
    def test_interior_vertex_configuration(self, mode):
        """Around every interior vertex the tile sizes must match the
        tiling's vertex configuration (e.g. 3.3.4.3.4)."""
        config, _ = _ARCH_CONFIGS[mode]
        board = archimedean_board(mode, 6, 5)
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

    @pytest.mark.parametrize("mode", sorted(_ARCH_CONFIGS))
    def test_no_overlapping_tiles(self, mode):
        # any edge shared by more than two tiles means overlap
        board = archimedean_board(mode, 6, 5)
        edge_count = defaultdict(int)
        for polygon in board.polygons.values():
            n = len(polygon)
            for i in range(n):
                a = (round(polygon[i][0], 6), round(polygon[i][1], 6))
                b = (round(polygon[(i + 1) % n][0], 6), round(polygon[(i + 1) % n][1], 6))
                edge_count[frozenset((a, b))] += 1
        assert all(count <= 2 for count in edge_count.values())

    def test_snub_dodecahedron_is_12_pentagons_80_triangles(self):
        board = snub_dodecahedron_board(10)
        sizes = sorted(len(p) for p in board.polygons.values())
        assert len(board.adjacency) == 92
        assert sizes.count(3) == 80 and sizes.count(5) == 12


def _corner_fans(board):
    """Cell sizes around each distinct polygon corner of a 3D board."""
    at_vertex = defaultdict(list)
    for polygon in board.polygons.values():
        for point in polygon:
            key = tuple(round(c, 6) for c in point)
            at_vertex[key].append(len(polygon))
    return at_vertex


def _boundary_components(board):
    """Connected components of the edges that belong to only one cell."""
    count = defaultdict(int)
    for polygon in board.polygons.values():
        points = [tuple(round(c, 6) for c in p) for p in polygon]
        for a, b in zip(points, points[1:] + points[:1]):
            count[frozenset((a, b))] += 1
    graph = defaultdict(set)
    for edge, cells in count.items():
        if cells == 1:
            a, b = edge
            graph[a].add(b)
            graph[b].add(a)
    seen, components = set(), 0
    for start in graph:
        if start in seen:
            continue
        components += 1
        stack = [start]
        while stack:
            vertex = stack.pop()
            if vertex not in seen:
                seen.add(vertex)
                stack.extend(graph[vertex] - seen)
    return components


class TestWrappedArchimedean:
    """The two-shape tilings wrapped onto the donut, cylinder and
    Möbius strip."""

    WRAPPED = [
        mode
        for mode in MODE_LABELS
        if mode.startswith(("torus", "mobius", "cyl"))
        and not mode.startswith(("torus2", "torus3"))  # chi != 0: see below
        and any(mode.endswith(tiling) for tiling in _ARCH_CONFIGS)
    ]

    @pytest.mark.parametrize("tiling", sorted(_ARCH_CONFIGS))
    def test_torus_vertex_configuration_everywhere(self, tiling):
        """A torus has no boundary, so every single vertex must show the
        tiling's full vertex configuration."""
        board = build_board("torus" + tiling, "easy")
        config = sorted(_ARCH_CONFIGS[tiling][0])
        for fan in _corner_fans(board).values():
            assert sorted(fan) == config

    @pytest.mark.parametrize("mode", sorted(WRAPPED))
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
        closed, a cylinder has two rims, a Möbius strip has one."""
        board = build_board(mode, "easy")
        want = {"torus": 0, "cyl": 2, "mobius": 1}[
            next(p for p in ("torus", "mobius", "cyl") if mode.startswith(p))
        ]
        assert _boundary_components(board) == want

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


class TestMultiTorus:
    """The double and triple tori: connected sums of torus lobes joined
    by tubes of quadrilaterals."""

    MODES = {
        mode: holes
        for holes in (2, 3)
        for mode in MODE_LABELS
        if mode.startswith(f"torus{holes}")
    }

    @pytest.mark.parametrize("mode", sorted(MODES))
    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_euler_characteristic_matches_the_genus(self, mode, difficulty):
        # a closed orientable surface with g holes has chi = 2 - 2g
        board = build_board(mode, difficulty)
        vertices = len(_corner_fans(board))
        edges = set()
        for polygon in board.polygons.values():
            points = [tuple(round(c, 6) for c in p) for p in polygon]
            for a, b in zip(points, points[1:] + points[:1]):
                edges.add(frozenset((a, b)))
        genus = self.MODES[mode]
        assert vertices - len(edges) + len(board.polygons) == 2 - 2 * genus

    @pytest.mark.parametrize("mode", sorted(MODES))
    def test_surface_is_closed(self, mode):
        assert _boundary_components(build_board(mode, "easy")) == 0

    @pytest.mark.parametrize("mode", sorted(MODES))
    def test_lobes_are_connected_through_the_bridges(self, mode):
        board = build_board(mode, "easy")
        seen: set = set()
        stack = [next(iter(board.adjacency))]
        while stack:
            cell = stack.pop()
            if cell not in seen:
                seen.add(cell)
                stack.extend(set(board.adjacency[cell]) - seen)
        assert len(seen) == len(board.adjacency)

    @pytest.mark.parametrize("tiling", sorted(_ARCH_CONFIGS))
    def test_cells_are_tiling_shapes_or_bridge_quads(self, tiling):
        for holes in (2, 3):
            board = build_board(f"torus{holes}{tiling}", "easy")
            allowed = set(_ARCH_CONFIGS[tiling][0]) | {4}
            assert {len(p) for p in board.polygons.values()} <= allowed

    def test_number_of_holes_must_leave_two_hole_cells(self):
        with pytest.raises(ValueError):
            multi_torus_board("trunchex", 2, 1, 1, 1)


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
