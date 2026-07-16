"""Difficulty presets and the build_board entry point.

The regular tilings and one-off solids keep an explicit preset per
mode. The Archimedean tilings are declared once in the ARCH_PRESETS
table (tiling -> surface -> difficulty -> builder args) and their
_PRESETS lambdas are generated from it -- adding an Archimedean
tiling is one ARCH_PRESETS row. See AGENTS.md.
"""

from __future__ import annotations

from minesweeper.boards.aperiodic import hat_board, penrose_board
from minesweeper.boards.catalog import mode_for
from minesweeper.boards.core import DIFFICULTIES, ROOT3, Board, Board3D
from minesweeper.boards.solids import (
    c80_board,
    c180_board,
    cube_board,
    cube_frame_board,
    snub_dodecahedron_board,
    sphere_board,
    sphere_triangle_board,
    stepped_bipyramid_board,
    tetrahedron_board,
    tetrahedron_frame_board,
)
from minesweeper.boards.surfaces import (
    arch_cylinder_board,
    arch_mobius_board,
    arch_torus_board,
    cylinder_board,
    cylinder_hex_board,
    cylinder_triangle_board,
    klein_board,
    mobius_board,
    mobius_hex_board,
    mobius_triangle_board,
    torus_board,
    torus_hex_board,
    torus_triangle_board,
)
from minesweeper.boards.tilings import (
    archimedean_board,
    hex_board,
    hexhex_board,
    square_board,
    triangle_board,
    triangle_grid_board,
)

# Explicit presets for the regular tilings and the one-off boards.
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
    "klein": {
        "easy": lambda: klein_board(12, 6, 9),
        "medium": lambda: klein_board(16, 8, 20),
        "hard": lambda: klein_board(24, 10, 48),
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
}


# Archimedean presets: tiling -> surface -> difficulty -> builder args
# (after the tiling name). flat: (nx, ny, mines, scale); torus:
# (nx, ny, mines, tube_radius); cylinder: (ring, rows, mines[, cut]);
# mobius: (ring, rows, mines). Hand-tuned so each board reads square
# and its rims/seam land cleanly.
ARCH_PRESETS = {
    "elongated": {
        "flat": {"easy": (7, 2, 14, 57), "medium": (10, 3, 30, 43), "hard": (14, 4, 67, 30)},
        "torus": {"easy": (12, 1, 9, 0.31), "medium": (14, 2, 26, 0.53), "hard": (20, 2, 48, 0.37)},
        "cylinder": {"easy": (10, 1 + 1 / (2 + ROOT3), 8, -0.5), "medium": (12, 2 + 1 / (2 + ROOT3), 24, -0.5), "hard": (15, 3 + 1 / (2 + ROOT3), 60, -0.5)},
        "mobius": {"easy": (12, 1, 9), "medium": (12, 2, 22), "hard": (18, 2, 43)},
    },
    "snubsquare": {
        "flat": {"easy": (4, 4, 15, 54), "medium": (5, 5, 26, 45), "hard": (7, 7, 57, 33)},
        "torus": {"easy": (5, 2, 8, 0.40), "medium": (7, 3, 19, 0.43), "hard": (10, 4, 48, 0.40)},
        "cylinder": {"easy": (5, 2, 8), "medium": (7, 3, 19), "hard": (9, 5, 57)},
        "mobius": {"easy": (13, 2, 10), "medium": (15, 3, 20), "hard": (17, 4, 41)},
    },
    "kagome": {
        "flat": {"easy": (5, 3, 14, 40), "medium": (7, 4, 30, 30), "hard": (9, 6, 65, 22)},
        "torus": {"easy": (8, 2, 12, 0.43), "medium": (10, 2, 18, 0.35), "hard": (12, 3, 43, 0.43)},
        "cylinder": {"easy": (6, 2, 9, ROOT3 / 2), "medium": (9, 3, 24, ROOT3 / 2), "hard": (11, 4, 55, ROOT3 / 2)},
        "mobius": {"easy": (12, 1, 9), "medium": (12, 2, 22), "hard": (18, 2, 43)},
    },
    "snubhex": {
        "flat": {"easy": (3, 2, 16, 44), "medium": (4, 2, 24, 39), "hard": (5, 3, 50, 32)},
        "torus": {"easy": (4, 1, 9, 0.43), "medium": (6, 1, 16, 0.29), "hard": (7, 2, 50, 0.49)},
        "cylinder": {"easy": (4, 1, 9, 21**0.5 / 4), "medium": (5, 2, 27, 21**0.5 / 4), "hard": (7, 2, 53, 21**0.5 / 4)},
    },
    "truncsquare": {
        "flat": {"easy": (6, 6, 12, 29), "medium": (9, 9, 29, 21), "hard": (13, 13, 68, 15)},
        "torus": {"easy": (9, 4, 9, 0.44), "medium": (12, 6, 22, 0.50), "hard": (16, 7, 45, 0.44)},
        "cylinder": {"easy": (9, 3, 7), "medium": (12, 5, 18), "hard": (16, 7, 45)},
        "mobius": {"easy": (12, 3, 9), "medium": (16, 4, 19), "hard": (22, 5, 44)},
    },
    "trunchex": {
        "flat": {"easy": (6, 3, 16, 19), "medium": (8, 4, 33, 14), "hard": (10, 6, 70, 11)},
        "torus": {"easy": (7, 2, 10, 0.49), "medium": (10, 2, 18, 0.35), "hard": (12, 3, 43, 0.43)},
        "cylinder": {"easy": (6, 2, 9, 0.5 + ROOT3 / 2), "medium": (8, 3, 22, 0.5 + ROOT3 / 2), "hard": (10, 4, 48, 0.5 + ROOT3 / 2)},
        "mobius": {"easy": (9, 1, 7), "medium": (10, 2, 18), "hard": (12, 3, 43)},
    },
    "rhombitrihex": {
        "flat": {"easy": (4, 2, 15, 38), "medium": (5, 3, 30, 32), "hard": (7, 4, 65, 23)},
        "torus": {"easy": (5, 2, 17, 0.40), "medium": (7, 2, 26, 0.40), "hard": (8, 3, 45, 0.43)},
        "cylinder": {"easy": (4, 2, 14), "medium": (5, 3, 28), "hard": (7, 3, 40)},
        "mobius": {"easy": (4, 2, 14), "medium": (6, 2, 22), "hard": (8, 3, 45)},
    },
    "trunctrihex": {
        "flat": {"easy": (4, 2, 15, 21), "medium": (5, 3, 30, 18), "hard": (7, 4, 65, 13)},
        "torus": {"easy": (5, 2, 17, 0.40), "medium": (7, 2, 26, 0.40), "hard": (8, 3, 45, 0.43)},
        "cylinder": {"easy": (4, 2, 14), "medium": (5, 3, 28), "hard": (7, 3, 40)},
        "mobius": {"easy": (4, 2, 14), "medium": (6, 2, 22), "hard": (8, 3, 45)},
    },
    # Laves (dual) tilings: same fundamental domain as the Archimedean tiling
    # they dualise, so the windows/seams carry over; only the mine counts are
    # retuned to the dual's (different) tile counts.
    "prismaticpent": {
        "flat": {"easy": (7, 2, 9, 57), "medium": (10, 3, 20, 43), "hard": (14, 4, 43, 30)},
        "torus": {"easy": (12, 1, 6, 0.31), "medium": (14, 2, 17, 0.53), "hard": (20, 2, 32, 0.37)},
        "cylinder": {"easy": (10, 1 + 1 / (2 + ROOT3), 5, -0.5), "medium": (12, 2 + 1 / (2 + ROOT3), 15, -0.5), "hard": (15, 3 + 1 / (2 + ROOT3), 38, -0.5)},
        "mobius": {"easy": (12, 1, 6), "medium": (12, 2, 15), "hard": (18, 2, 29)},
    },
    "cairo": {
        "flat": {"easy": (4, 4, 9, 54), "medium": (5, 5, 16, 45), "hard": (7, 7, 36, 33)},
        "torus": {"easy": (5, 2, 5, 0.40), "medium": (7, 3, 13, 0.43), "hard": (10, 4, 32, 0.40)},
        "cylinder": {"easy": (5, 2, 5), "medium": (7, 3, 13), "hard": (9, 5, 38)},
        "mobius": {"easy": (13, 2, 7), "medium": (15, 3, 13), "hard": (17, 4, 27)},
    },
    "rhombille": {
        "flat": {"easy": (5, 3, 13, 40), "medium": (7, 4, 28, 30), "hard": (9, 6, 61, 22)},
        "torus": {"easy": (8, 2, 12, 0.43), "medium": (10, 2, 18, 0.35), "hard": (12, 3, 43, 0.43)},
        "cylinder": {"easy": (6, 2, 9, ROOT3 / 2), "medium": (9, 3, 24, ROOT3 / 2), "hard": (11, 4, 55, ROOT3 / 2)},
        "mobius": {"easy": (12, 1, 9), "medium": (12, 2, 22), "hard": (18, 2, 43)},
    },
    "floret": {
        "flat": {"easy": (3, 2, 10, 44), "medium": (4, 2, 15, 39), "hard": (5, 3, 33, 32)},
        "torus": {"easy": (4, 1, 6, 0.43), "medium": (6, 1, 11, 0.29), "hard": (7, 2, 33, 0.49)},
        "cylinder": {"easy": (4, 1, 6, 21**0.5 / 4), "medium": (5, 2, 18, 21**0.5 / 4), "hard": (7, 2, 35, 21**0.5 / 4)},
    },
    "tetrakis": {
        "flat": {"easy": (6, 6, 20, 29), "medium": (9, 9, 52, 21), "hard": (13, 13, 126, 15)},
        "torus": {"easy": (9, 4, 18, 0.44), "medium": (12, 6, 44, 0.50), "hard": (16, 7, 90, 0.44)},
        "cylinder": {"easy": (9, 3, 14), "medium": (12, 5, 36), "hard": (16, 7, 90)},
        "mobius": {"easy": (12, 3, 18), "medium": (16, 4, 38), "hard": (22, 5, 88)},
    },
    "triakis": {
        "flat": {"easy": (6, 3, 30, 19), "medium": (8, 4, 62, 14), "hard": (10, 6, 134, 11)},
        "torus": {"easy": (7, 2, 20, 0.49), "medium": (10, 2, 36, 0.35), "hard": (12, 3, 86, 0.43)},
        "cylinder": {"easy": (6, 2, 18, 0.5 + ROOT3 / 2), "medium": (8, 3, 44, 0.5 + ROOT3 / 2), "hard": (10, 4, 96, 0.5 + ROOT3 / 2)},
        "mobius": {"easy": (9, 1, 14), "medium": (10, 2, 36), "hard": (12, 3, 86)},
    },
    "deltoidal": {
        "flat": {"easy": (4, 2, 13, 38), "medium": (5, 3, 30, 32), "hard": (7, 4, 62, 23)},
        "torus": {"easy": (5, 2, 17, 0.40), "medium": (7, 2, 26, 0.40), "hard": (8, 3, 45, 0.43)},
        "cylinder": {"easy": (4, 2, 14), "medium": (5, 3, 28), "hard": (7, 3, 40)},
        "mobius": {"easy": (4, 2, 14), "medium": (6, 2, 22), "hard": (8, 3, 45)},
    },
    "kisrhombille": {
        "flat": {"easy": (4, 2, 27, 21), "medium": (5, 3, 60, 18), "hard": (7, 4, 125, 13)},
        "torus": {"easy": (5, 2, 34, 0.40), "medium": (7, 2, 52, 0.40), "hard": (8, 3, 90, 0.43)},
        "cylinder": {"easy": (4, 2, 28), "medium": (5, 3, 56), "hard": (7, 3, 80)},
        "mobius": {"easy": (4, 2, 28), "medium": (6, 2, 44), "hard": (8, 3, 90)},
    },
}

_ARCH_BUILDERS = {
    "flat": archimedean_board,
    "torus": arch_torus_board,
    "cylinder": arch_cylinder_board,
    "mobius": arch_mobius_board,
}

for _tiling, _surfaces in ARCH_PRESETS.items():
    for _surface, _by_difficulty in _surfaces.items():
        _builder = _ARCH_BUILDERS[_surface]
        _PRESETS[mode_for(_tiling, _surface)] = {
            _difficulty: (lambda b=_builder, t=_tiling, p=_params: b(t, *p))
            for _difficulty, _params in _by_difficulty.items()
        }


def build_board(mode: str, difficulty: str) -> Board | Board3D:
    if mode not in _PRESETS:
        raise ValueError(f"unknown mode {mode!r}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    return _PRESETS[mode][difficulty]()
