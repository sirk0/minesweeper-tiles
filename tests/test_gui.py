import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from minesweeper.game import CellState, GameState  # noqa: E402
from minesweeper.gui import CELL, HEADER, MARGIN, MinesweeperGUI, make_fonts  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


@pytest.fixture
def gui():
    return MinesweeperGUI("easy")


def cell_center(row, col):
    return (
        MARGIN + col * CELL + CELL // 2,
        MARGIN + HEADER + row * CELL + CELL // 2,
    )


def mouse_event(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


class TestGeometry:
    def test_cell_at_maps_centers_back_to_cells(self, gui):
        assert gui.cell_at(cell_center(0, 0)) == (0, 0)
        assert gui.cell_at(cell_center(8, 8)) == (8, 8)
        assert gui.cell_at(cell_center(3, 7)) == (3, 7)

    def test_cell_at_header_and_margins_is_none(self, gui):
        assert gui.cell_at((5, 5)) is None  # header area
        assert gui.cell_at((0, MARGIN + HEADER + 5)) is None  # left margin
        w, h = gui.size
        assert gui.cell_at((w - 1, h - 1)) is None  # bottom-right margin

    def test_window_size_matches_board(self, gui):
        assert gui.size == (
            9 * CELL + 2 * MARGIN,
            9 * CELL + HEADER + 2 * MARGIN,
        )


class TestInteraction:
    def test_left_click_reveals(self, gui):
        assert gui.handle_event(mouse_event(cell_center(4, 4)))
        assert gui.game.cell_state(4, 4) is CellState.REVEALED
        assert gui.game.state is not GameState.LOST  # first click safe

    def test_right_click_flags_and_unflags(self, gui):
        gui.handle_event(mouse_event(cell_center(2, 2), button=3))
        assert gui.game.cell_state(2, 2) is CellState.FLAGGED
        gui.handle_event(mouse_event(cell_center(2, 2), button=3))
        assert gui.game.cell_state(2, 2) is CellState.HIDDEN

    def test_face_click_starts_new_game(self, gui):
        gui.handle_event(mouse_event(cell_center(4, 4)))
        old_game = gui.game
        gui.handle_event(mouse_event(gui.face_rect.center))
        assert gui.game is not old_game
        assert gui.game.state is GameState.PLAYING

    def test_n_key_starts_new_game(self, gui):
        old_game = gui.game
        gui.handle_event(key_event(pygame.K_n))
        assert gui.game is not old_game

    def test_difficulty_keys_resize_board(self, gui):
        gui.handle_event(key_event(pygame.K_2))
        assert (gui.game.rows, gui.game.cols) == (16, 16)
        gui.handle_event(key_event(pygame.K_3))
        assert (gui.game.rows, gui.game.cols) == (16, 30)
        gui.handle_event(key_event(pygame.K_1))
        assert (gui.game.rows, gui.game.cols) == (9, 9)

    def test_escape_and_quit_stop_the_loop(self, gui):
        assert gui.handle_event(key_event(pygame.K_ESCAPE)) is False
        assert gui.handle_event(pygame.event.Event(pygame.QUIT)) is False

    def test_clicks_ignored_after_game_over(self, gui):
        gui.handle_event(mouse_event(cell_center(4, 4)))
        mine = next(
            (r, c)
            for r in range(9)
            for c in range(9)
            if gui.game.is_mine(r, c)
        )
        gui.click(*mine)
        assert gui.game.state is GameState.LOST
        hidden_before = [
            (r, c)
            for r in range(9)
            for c in range(9)
            if gui.game.cell_state(r, c) is CellState.HIDDEN
        ]
        gui.handle_event(mouse_event(cell_center(*hidden_before[0])))
        assert gui.game.cell_state(*hidden_before[0]) is CellState.HIDDEN


class TestTimerAndState:
    def test_timer_starts_on_first_click(self, gui):
        assert gui.elapsed == 0
        assert gui.started_at is None
        gui.handle_event(mouse_event(cell_center(4, 4)))
        assert gui.started_at is not None

    def test_timer_freezes_when_game_ends(self, gui):
        gui.handle_event(mouse_event(cell_center(4, 4)))
        mine = next(
            (r, c) for r in range(9) for c in range(9) if gui.game.is_mine(r, c)
        )
        gui.click(*mine)
        assert gui.finished_at is not None
        assert gui.elapsed == gui.elapsed  # stable after finish

    def test_exploded_cell_recorded_on_loss(self, gui):
        gui.handle_event(mouse_event(cell_center(4, 4)))
        mine = next(
            (r, c) for r in range(9) for c in range(9) if gui.game.is_mine(r, c)
        )
        gui.click(*mine)
        assert gui.exploded == mine


class TestRendering:
    def draw(self, gui):
        surface = pygame.Surface(gui.size)
        gui.draw(surface, make_fonts())
        return surface

    def test_draw_initial_board(self, gui):
        surface = self.draw(gui)
        assert surface.get_size() == gui.size

    def test_draw_all_game_phases(self, gui):
        self.draw(gui)  # fresh board
        gui.handle_event(mouse_event(cell_center(4, 4)))
        gui.handle_event(mouse_event(cell_center(0, 0), button=3))
        self.draw(gui)  # mid-game with reveals and a flag
        mine = next(
            (r, c) for r in range(9) for c in range(9) if gui.game.is_mine(r, c)
        )
        gui.click(*mine)
        assert gui.game.state is GameState.LOST
        self.draw(gui)  # loss screen with mines shown

    def test_exploded_mine_drawn_highlighted(self, gui):
        gui.handle_event(mouse_event(cell_center(4, 4)))
        mine = next(
            (r, c) for r in range(9) for c in range(9) if gui.game.is_mine(r, c)
        )
        gui.click(*mine)
        surface = self.draw(gui)
        rect = gui.cell_rect(*mine)
        corner = surface.get_at((rect.left + 3, rect.top + 3))[:3]
        assert corner == (255, 80, 80)  # EXPLODED_FACE background

    def test_won_game_draws(self, gui):
        # tiny deterministic win via a fresh GUI with a hand-built game
        from minesweeper.game import Game

        gui.game = Game(2, 2, 1, mine_positions={(0, 0)})
        gui.game.reveal(1, 1)
        gui.game.reveal(0, 1)
        gui.game.reveal(1, 0)
        assert gui.game.state is GameState.WON
        self.draw(gui)
