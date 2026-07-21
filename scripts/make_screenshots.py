"""Render mid-game board screenshots for the README.

Drives the real GUI screens headlessly: seed the rng, reveal a patch of
cells, flag a few real mines, optionally detonate one, then save the
supersampled canvas downscaled to the size a player actually sees.

Usage: PYTHONPATH=. python scripts/make_screenshots.py [output_dir]
       (default output dir: docs/screenshots)
"""

from __future__ import annotations

import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from minesweeper.game import CellState  # noqa: E402
from minesweeper.gui import (  # noqa: E402
    HEADER,
    MARGIN,
    FontCache,
    GameScreen3D,
    S,
    make_screen,
)

# mode, difficulty, seed, revealed fraction, flag count, explode?, rotation nudge
SHOTS = [
    ("c180", "medium", 7, 0.30, 5, False, (0, 0)),
    ("mobiushex", "medium", 3, 0.32, 4, False, (0, 0)),
    ("penrose", "medium", 11, 0.42, 5, False, (0, 0)),
    ("torussnubsquare", "medium", 5, 0.34, 5, True, (0, 0)),
]

FILENAMES = {
    "c180": "c180.png",
    "mobiushex": "mobiushex.png",
    "penrose": "penrose.png",
    "torussnubsquare": "torussnubsquare-lost.png",
}


def centroid(points):
    n = len(points)
    return (sum(x for x, *_ in points) / n, sum(p[1] for p in points) / n)


def board_center_2d(screen):
    return (screen.board.width / 2, screen.board.height / 2)


def viewport_center(screen):
    return (screen.size[0] / 2, MARGIN + HEADER + screen.VIEWPORT / 2)


def front_cells_by_distance(screen):
    """3D: cells currently drawn (front faces / near side), nearest the
    viewport centre first."""
    cx, cy = viewport_center(screen)
    entries = screen._project()  # (depth, cell, polygon, center, radius, shade)
    # near side first for two-sided surfaces: keep the front half by depth
    if screen.board.two_sided:
        ordered = sorted(entries, key=lambda e: e[0], reverse=True)
        entries = ordered[: max(1, len(ordered) // 2)]
    ranked = sorted(entries, key=lambda e: math.hypot(e[3][0] - cx, e[3][1] - cy))
    return [e[1] for e in ranked]


def ordered_cells(screen):
    """Cells to consider for reveals/flags, most central/front first."""
    if isinstance(screen, GameScreen3D):
        return front_cells_by_distance(screen)
    cx, cy = board_center_2d(screen)
    polys = screen.board.polygons
    return sorted(
        polys,
        key=lambda c: math.hypot(*(a - b for a, b in zip(centroid(polys[c]), (cx, cy)))),
    )


def revealed_count(game):
    return sum(1 for c in game.cells if game.cell_state(c) is CellState.REVEALED)


def build_shot(mode, difficulty, seed, frac, flags, explode, nudge):
    screen = make_screen(mode, difficulty)
    if isinstance(screen, GameScreen3D) and nudge != (0, 0):
        screen.rotate(*nudge)
    screen.game._rng.seed(seed)

    order = ordered_cells(screen)
    game = screen.game

    # open a central patch (first reveal is always safe and flood-fills)
    screen.click(order[0])

    # grow into a connected open region by flooding from central empty
    # cells (adjacent_mines == 0), up to the target revealed fraction
    target = int(len(game.cells) * frac)
    for cell in order:
        if revealed_count(game) >= target:
            break
        if (
            game.cell_state(cell) is CellState.HIDDEN
            and not game.is_mine(cell)
            and game.adjacent_mines(cell) == 0
        ):
            screen.click(cell)

    # flag real mines sitting on the frontier of the revealed region
    def is_frontier_mine(cell):
        return (
            game.is_mine(cell)
            and game.cell_state(cell) is CellState.HIDDEN
            and any(
                game.cell_state(n) is CellState.REVEALED for n in game.neighbors(cell)
            )
        )

    frontier_mines = [c for c in order if is_frontier_mine(c)]

    # for the failure shot, reserve the most central frontier mine to
    # detonate and flag the rest; the GUI reveals every other mine on loss
    detonator = frontier_mines.pop(0) if explode and frontier_mines else None
    for cell in frontier_mines[:flags]:
        game.toggle_flag(cell)
    if detonator is not None:
        screen.click(detonator)

    return screen


def render(screen, path):
    w, h = screen.size
    canvas = pygame.Surface((w, h))
    screen.draw(canvas, FontCache())
    out = pygame.transform.smoothscale(canvas, (w // S, h // S))
    pygame.image.save(out, path)


def main() -> int:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots"
    os.makedirs(out_dir, exist_ok=True)

    pygame.init()
    pygame.display.set_mode((1, 1))
    for mode, *args in SHOTS:
        screen = build_shot(mode, *args)
        path = os.path.join(out_dir, FILENAMES[mode])
        render(screen, path)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
