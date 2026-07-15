from __future__ import annotations

from minesweeper.boards.core import Board, Board3D, DIFFICULTIES, ROOT3
from minesweeper.boards.tilings import archimedean_board, hex_board, hexhex_board, square_board, triangle_board, triangle_grid_board
from minesweeper.boards.aperiodic import hat_board, penrose_board
from minesweeper.boards.solids import c180_board, c80_board, cube_board, cube_frame_board, snub_dodecahedron_board, sphere_board, sphere_triangle_board, stepped_bipyramid_board, tetrahedron_board, tetrahedron_frame_board
from minesweeper.boards.surfaces import arch_cylinder_board, arch_mobius_board, arch_torus_board, cylinder_board, cylinder_hex_board, cylinder_triangle_board, mobius_board, mobius_hex_board, mobius_triangle_board, torus_board, torus_hex_board, torus_triangle_board




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
    # Flat Archimedean tilings: a roughly nx x ny domain
    # rectangle centred on a rotation centre of the tiling -- a clean,
    # symmetric block (see archimedean_board), rather than a round disc.
    "elongated": {
        "easy": lambda: archimedean_board("elongated", 7, 2, 14, scale=57),
        "medium": lambda: archimedean_board("elongated", 10, 3, 30, scale=43),
        "hard": lambda: archimedean_board("elongated", 14, 4, 67, scale=30),
    },
    "snubsquare": {
        "easy": lambda: archimedean_board("snubsquare", 4, 4, 15, scale=54),
        "medium": lambda: archimedean_board("snubsquare", 5, 5, 26, scale=45),
        "hard": lambda: archimedean_board("snubsquare", 7, 7, 57, scale=33),
    },
    "kagome": {
        "easy": lambda: archimedean_board("kagome", 5, 3, 14, scale=40),
        "medium": lambda: archimedean_board("kagome", 7, 4, 30, scale=30),
        "hard": lambda: archimedean_board("kagome", 9, 6, 65, scale=22),
    },
    "snubhex": {
        "easy": lambda: archimedean_board("snubhex", 3, 2, 16, scale=44),
        "medium": lambda: archimedean_board("snubhex", 4, 2, 24, scale=39),
        "hard": lambda: archimedean_board("snubhex", 5, 3, 50, scale=32),
    },
    "truncsquare": {
        "easy": lambda: archimedean_board("truncsquare", 6, 6, 12, scale=29),
        "medium": lambda: archimedean_board("truncsquare", 9, 9, 29, scale=21),
        "hard": lambda: archimedean_board("truncsquare", 13, 13, 68, scale=15),
    },
    "trunchex": {
        "easy": lambda: archimedean_board("trunchex", 6, 3, 16, scale=19),
        "medium": lambda: archimedean_board("trunchex", 8, 4, 33, scale=14),
        "hard": lambda: archimedean_board("trunchex", 10, 6, 70, scale=11),
    },
    "rhombitrihex": {
        "easy": lambda: archimedean_board("rhombitrihex", 4, 2, 15, scale=38),
        "medium": lambda: archimedean_board("rhombitrihex", 5, 3, 30, scale=32),
        "hard": lambda: archimedean_board("rhombitrihex", 7, 4, 65, scale=23),
    },
    "trunctrihex": {
        "easy": lambda: archimedean_board("trunctrihex", 4, 2, 15, scale=21),
        "medium": lambda: archimedean_board("trunctrihex", 5, 3, 30, scale=18),
        "hard": lambda: archimedean_board("trunctrihex", 7, 4, 65, scale=13),
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
    "torusrhombitrihex": {
        "easy": lambda: arch_torus_board("rhombitrihex", 5, 2, 17, 0.40),
        "medium": lambda: arch_torus_board("rhombitrihex", 7, 2, 26, 0.40),
        "hard": lambda: arch_torus_board("rhombitrihex", 8, 3, 45, 0.43),
    },
    "torustrunctrihex": {
        "easy": lambda: arch_torus_board("trunctrihex", 5, 2, 17, 0.40),
        "medium": lambda: arch_torus_board("trunctrihex", 7, 2, 26, 0.40),
        "hard": lambda: arch_torus_board("trunctrihex", 8, 3, 45, 0.43),
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
    "mobiusrhombitrihex": {
        "easy": lambda: arch_mobius_board("rhombitrihex", 4, 2, 14),
        "medium": lambda: arch_mobius_board("rhombitrihex", 6, 2, 22),
        "hard": lambda: arch_mobius_board("rhombitrihex", 8, 3, 45),
    },
    "mobiustrunctrihex": {
        "easy": lambda: arch_mobius_board("trunctrihex", 4, 2, 14),
        "medium": lambda: arch_mobius_board("trunctrihex", 6, 2, 22),
        "hard": lambda: arch_mobius_board("trunctrihex", 8, 3, 45),
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
    # the three-shape tilings have no full-width horizontal edge-line, so
    # their cylinder rims are left as clean whole-cell zigzags (cut=0)
    "cylrhombitrihex": {
        "easy": lambda: arch_cylinder_board("rhombitrihex", 4, 2, 14),
        "medium": lambda: arch_cylinder_board("rhombitrihex", 5, 3, 28),
        "hard": lambda: arch_cylinder_board("rhombitrihex", 7, 3, 40),
    },
    "cyltrunctrihex": {
        "easy": lambda: arch_cylinder_board("trunctrihex", 4, 2, 14),
        "medium": lambda: arch_cylinder_board("trunctrihex", 5, 3, 28),
        "hard": lambda: arch_cylinder_board("trunctrihex", 7, 3, 40),
    },
}


def build_board(mode: str, difficulty: str) -> Board | Board3D:
    if mode not in _PRESETS:
        raise ValueError(f"unknown mode {mode!r}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    return _PRESETS[mode][difficulty]()
