"""Pygame GUI for minesweeper.

Run with ``python -m minesweeper`` (or ``python -m minesweeper.gui``).
Controls: left-click reveals (on a revealed number: chords), right-click
flags, the face button or ``n`` restarts, ``1``/``2``/``3`` switch
difficulty, ``Escape`` quits.
"""

from __future__ import annotations

import argparse
import sys
import time

import pygame

from minesweeper.cli import DIFFICULTIES
from minesweeper.game import CellState, Game, GameState

CELL = 32
HEADER = 52
MARGIN = 8

BG = (192, 192, 192)
BEVEL_LIGHT = (255, 255, 255)
BEVEL_DARK = (128, 128, 128)
HIDDEN_FACE = (189, 189, 189)
REVEALED_FACE = (222, 222, 222)
EXPLODED_FACE = (255, 80, 80)
GRID_LINE = (160, 160, 160)
COUNTER_BG = (40, 0, 0)
COUNTER_FG = (255, 40, 40)

NUMBER_COLORS = {
    1: (0, 0, 255),
    2: (0, 128, 0),
    3: (255, 0, 0),
    4: (0, 0, 128),
    5: (128, 0, 0),
    6: (0, 128, 128),
    7: (0, 0, 0),
    8: (128, 128, 128),
}

FACES = {"playing": ":)", "won": "B)", "lost": "X(", "pressed": ":o"}


class MinesweeperGUI:
    def __init__(self, difficulty: str = "easy") -> None:
        self.difficulty = difficulty
        self.exploded: tuple[int, int] | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.new_game()

    # -- game lifecycle ---------------------------------------------------

    def new_game(self, difficulty: str | None = None) -> None:
        if difficulty is not None:
            self.difficulty = difficulty
        rows, cols, mines = DIFFICULTIES[self.difficulty]
        self.game = Game(rows, cols, mines)
        self.exploded = None
        self.started_at = None
        self.finished_at = None

    @property
    def elapsed(self) -> int:
        if self.started_at is None:
            return 0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return min(999, int(end - self.started_at))

    # -- geometry ---------------------------------------------------------

    @property
    def size(self) -> tuple[int, int]:
        return (
            self.game.cols * CELL + 2 * MARGIN,
            self.game.rows * CELL + HEADER + 2 * MARGIN,
        )

    def cell_at(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """Map a pixel position to (row, col), or None outside the board."""
        x, y = pos
        col = (x - MARGIN) // CELL
        row = (y - MARGIN - HEADER) // CELL
        if x < MARGIN or y < MARGIN + HEADER or not self.game.in_bounds(row, col):
            return None
        return row, col

    @property
    def face_rect(self) -> pygame.Rect:
        width = self.size[0]
        return pygame.Rect(width // 2 - 18, MARGIN + 4, 36, 36)

    # -- input ------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process one pygame event. Returns False when the app should quit."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_n:
                self.new_game()
            elif event.key == pygame.K_1:
                self.new_game("easy")
            elif event.key == pygame.K_2:
                self.new_game("medium")
            elif event.key == pygame.K_3:
                self.new_game("hard")
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.face_rect.collidepoint(event.pos):
                self.new_game()
                return True
            cell = self.cell_at(event.pos)
            if cell is not None:
                if event.button == 1:
                    self.click(*cell)
                elif event.button == 3:
                    self.game.toggle_flag(*cell)
        return True

    def click(self, row: int, col: int) -> None:
        """Left-click: reveal a hidden cell, chord a revealed one."""
        if self.game.state is not GameState.PLAYING:
            return
        if self.started_at is None:
            self.started_at = time.monotonic()
        if self.game.cell_state(row, col) is CellState.REVEALED:
            self.game.chord(row, col)
        else:
            self.game.reveal(row, col)
        if self.game.state is GameState.LOST and self.exploded is None:
            self.exploded = self.find_exploded(row, col)
        if self.game.state is not GameState.PLAYING:
            self.finished_at = time.monotonic()

    def find_exploded(self, row: int, col: int) -> tuple[int, int]:
        """The mine that ended the game: the clicked cell or, after a bad
        chord, whichever revealed neighbor is a mine."""
        if self.game.is_mine(row, col):
            return row, col
        for r, c in self.game.neighbors(row, col):
            if (
                self.game.is_mine(r, c)
                and self.game.cell_state(r, c) is CellState.REVEALED
            ):
                return r, c
        return row, col

    # -- drawing ----------------------------------------------------------

    def draw(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        surface.fill(BG)
        self.draw_header(surface, fonts)
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                self.draw_cell(surface, fonts, r, c)

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        return pygame.Rect(MARGIN + col * CELL, MARGIN + HEADER + row * CELL, CELL, CELL)

    def draw_cell(
        self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font], row: int, col: int
    ) -> None:
        game = self.game
        rect = self.cell_rect(row, col)
        state = game.cell_state(row, col)
        game_over = game.state is not GameState.PLAYING
        show_mine = game_over and game.is_mine(row, col) and (
            game.state is GameState.LOST or state is not CellState.FLAGGED
        )

        if state is CellState.REVEALED or (show_mine and game.state is GameState.LOST):
            face = EXPLODED_FACE if (row, col) == self.exploded else REVEALED_FACE
            pygame.draw.rect(surface, face, rect)
            pygame.draw.rect(surface, GRID_LINE, rect, 1)
        else:
            pygame.draw.rect(surface, HIDDEN_FACE, rect)
            pygame.draw.line(surface, BEVEL_LIGHT, rect.topleft, rect.topright, 2)
            pygame.draw.line(surface, BEVEL_LIGHT, rect.topleft, rect.bottomleft, 2)
            pygame.draw.line(surface, BEVEL_DARK, rect.bottomleft, rect.bottomright, 2)
            pygame.draw.line(surface, BEVEL_DARK, rect.topright, rect.bottomright, 2)

        if show_mine and game.state is GameState.LOST:
            self.draw_mine(surface, rect)
        elif state is CellState.FLAGGED:
            wrong = game.state is GameState.LOST and not game.is_mine(row, col)
            self.draw_flag(surface, rect, wrong=wrong)
        elif game.state is GameState.WON and game.is_mine(row, col):
            self.draw_flag(surface, rect, wrong=False)  # auto-flag mines on win
        elif state is CellState.REVEALED and not game.is_mine(row, col):
            n = game.adjacent_mines(row, col)
            if n:
                text = fonts["cell"].render(str(n), True, NUMBER_COLORS[n])
                surface.blit(text, text.get_rect(center=rect.center))

    def draw_mine(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.circle(surface, (0, 0, 0), rect.center, CELL // 4)
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            length = CELL // 3
            start = (rect.centerx - dx * length, rect.centery - dy * length)
            end = (rect.centerx + dx * length, rect.centery + dy * length)
            pygame.draw.line(surface, (0, 0, 0), start, end, 2)

    def draw_flag(self, surface: pygame.Surface, rect: pygame.Rect, *, wrong: bool) -> None:
        pole_x = rect.centerx
        pygame.draw.line(
            surface, (0, 0, 0), (pole_x, rect.top + 7), (pole_x, rect.bottom - 8), 2
        )
        pygame.draw.polygon(
            surface,
            (255, 0, 0),
            [
                (pole_x, rect.top + 7),
                (pole_x - 10, rect.top + 12),
                (pole_x, rect.top + 17),
            ],
        )
        if wrong:  # misplaced flag revealed at game end
            pygame.draw.line(surface, (0, 0, 0), rect.topleft, rect.bottomright, 2)
            pygame.draw.line(surface, (0, 0, 0), rect.bottomleft, rect.topright, 2)

    def draw_header(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        width = self.size[0]

        counter = f"{max(-99, min(999, self.game.flags_remaining)):03d}"
        self.draw_counter(surface, fonts, counter, x=MARGIN + 4)

        timer = f"{self.elapsed:03d}"
        timer_width = fonts["counter"].size(timer)[0] + 12
        self.draw_counter(surface, fonts, timer, x=width - MARGIN - 4 - timer_width)

        rect = self.face_rect
        pygame.draw.rect(surface, HIDDEN_FACE, rect)
        pygame.draw.line(surface, BEVEL_LIGHT, rect.topleft, rect.topright, 2)
        pygame.draw.line(surface, BEVEL_LIGHT, rect.topleft, rect.bottomleft, 2)
        pygame.draw.line(surface, BEVEL_DARK, rect.bottomleft, rect.bottomright, 2)
        pygame.draw.line(surface, BEVEL_DARK, rect.topright, rect.bottomright, 2)
        face = FACES[self.game.state.value]
        text = fonts["face"].render(face, True, (0, 0, 0))
        surface.blit(text, text.get_rect(center=rect.center))

    def draw_counter(
        self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font], value: str, *, x: int
    ) -> None:
        text = fonts["counter"].render(value, True, COUNTER_FG)
        box = pygame.Rect(x, MARGIN + 6, text.get_width() + 12, 32)
        pygame.draw.rect(surface, COUNTER_BG, box)
        surface.blit(text, text.get_rect(center=box.center))

    # -- main loop --------------------------------------------------------

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Minesweeper")
        screen = pygame.display.set_mode(self.size)
        fonts = make_fonts()
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                running = self.handle_event(event)
                if not running:
                    break
                if screen.get_size() != self.size:  # difficulty changed
                    screen = pygame.display.set_mode(self.size)
            self.draw(screen, fonts)
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()


def make_fonts() -> dict[str, pygame.font.Font]:
    pygame.font.init()
    return {
        "cell": pygame.font.SysFont("menlo, couriernew, monospace", 20, bold=True),
        "counter": pygame.font.SysFont("menlo, couriernew, monospace", 24, bold=True),
        "face": pygame.font.SysFont("menlo, couriernew, monospace", 16, bold=True),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minesweeper-gui", description=__doc__)
    parser.add_argument(
        "difficulty",
        nargs="?",
        choices=sorted(DIFFICULTIES),
        default="easy",
        help="board preset (default: easy)",
    )
    args = parser.parse_args(argv)
    MinesweeperGUI(args.difficulty).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
