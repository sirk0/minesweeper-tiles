import pytest

from minesweeper.boards import (
    DIFFICULTIES,
    MODE_LABELS,
    MODES_3D,
    TOPOLOGIES,
    build_board,
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
    newell_normal,
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

    def test_every_mode_belongs_to_exactly_one_topology(self):
        modes = [m for _, tilings in TOPOLOGIES.values() for m in tilings]
        assert sorted(modes) == sorted(MODE_LABELS)
        assert len(modes) == len(set(modes))
