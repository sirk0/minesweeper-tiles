import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from minesweeper.boards import MODE_LABELS  # noqa: E402
from minesweeper.game import CellState, Game, GameState  # noqa: E402
from minesweeper.gui import (  # noqa: E402
    EXPLODED_FACE,
    FontCache,
    GameScreen,
    MenuScreen,
    point_in_polygon,
)


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


@pytest.fixture(scope="module")
def fonts():
    return FontCache()


@pytest.fixture
def gui():
    return GameScreen("square", "easy")


def mouse_event(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def find_mine(screen):
    return next(cell for cell in screen.game.cells if screen.game.is_mine(cell))


class TestGeometryHelpers:
    def test_point_in_polygon(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon((5, 5), square)
        assert not point_in_polygon((15, 5), square)
        triangle = [(0, 10), (10, 10), (5, 0)]
        assert point_in_polygon((5, 7), triangle)
        assert not point_in_polygon((1, 1), triangle)


class TestGameScreenGeometry:
    @pytest.mark.parametrize("mode", sorted(MODE_LABELS))
    def test_every_cell_center_maps_back_to_its_cell(self, mode):
        screen = GameScreen(mode, "easy")
        for cell, center in screen.centers.items():
            assert screen.cell_at(center) == cell

    def test_positions_outside_the_board_map_to_none(self, gui):
        assert gui.cell_at((2, 2)) is None  # header area
        w, h = gui.size
        assert gui.cell_at((w - 1, h - 1)) is None

    def test_window_fits_board(self, gui):
        w, h = gui.size
        assert w > gui.board.width and h > gui.board.height


class TestInteraction:
    def test_left_click_reveals(self, gui):
        cell = (4, 4)
        assert gui.handle_event(mouse_event(gui.centers[cell])) is None
        assert gui.game.cell_state(cell) is CellState.REVEALED
        assert gui.game.state is not GameState.LOST  # first click safe

    def test_right_click_flags_and_unflags(self, gui):
        pos = gui.centers[(2, 2)]
        gui.handle_event(mouse_event(pos, button=3))
        assert gui.game.cell_state((2, 2)) is CellState.FLAGGED
        gui.handle_event(mouse_event(pos, button=3))
        assert gui.game.cell_state((2, 2)) is CellState.HIDDEN

    def test_face_click_starts_new_game(self, gui):
        gui.handle_event(mouse_event(gui.centers[(4, 4)]))
        old_game = gui.game
        gui.handle_event(mouse_event(gui.face_rect.center))
        assert gui.game is not old_game
        assert gui.game.state is GameState.PLAYING

    def test_n_key_starts_new_game(self, gui):
        old_game = gui.game
        gui.handle_event(key_event(pygame.K_n))
        assert gui.game is not old_game

    def test_difficulty_keys_rebuild_board(self, gui):
        easy_cells = len(gui.game.cells)
        gui.handle_event(key_event(pygame.K_2))
        assert gui.difficulty == "medium"
        assert len(gui.game.cells) > easy_cells
        gui.handle_event(key_event(pygame.K_1))
        assert len(gui.game.cells) == easy_cells

    def test_escape_returns_to_menu(self, gui):
        assert gui.handle_event(key_event(pygame.K_ESCAPE)) == "menu"

    def test_quit_event(self, gui):
        assert gui.handle_event(pygame.event.Event(pygame.QUIT)) == "quit"

    def test_clicks_ignored_after_game_over(self, gui):
        gui.handle_event(mouse_event(gui.centers[(4, 4)]))
        gui.click(find_mine(gui))
        assert gui.game.state is GameState.LOST
        hidden = next(
            cell
            for cell in gui.game.cells
            if gui.game.cell_state(cell) is CellState.HIDDEN
        )
        gui.handle_event(mouse_event(gui.centers[hidden]))
        assert gui.game.cell_state(hidden) is CellState.HIDDEN

    @pytest.mark.parametrize("mode", sorted(MODE_LABELS))
    def test_click_reveals_in_every_mode(self, mode):
        screen = GameScreen(mode, "easy")
        cell = next(iter(screen.centers))
        screen.handle_event(mouse_event(screen.centers[cell]))
        assert screen.game.cell_state(cell) is CellState.REVEALED


class TestTimerAndState:
    def test_timer_starts_on_first_click(self, gui):
        assert gui.elapsed == 0
        assert gui.started_at is None
        gui.handle_event(mouse_event(gui.centers[(4, 4)]))
        assert gui.started_at is not None

    def test_timer_freezes_when_game_ends(self, gui):
        gui.handle_event(mouse_event(gui.centers[(4, 4)]))
        gui.click(find_mine(gui))
        assert gui.finished_at is not None

    def test_exploded_cell_recorded_on_loss(self, gui):
        gui.handle_event(mouse_event(gui.centers[(4, 4)]))
        mine = find_mine(gui)
        gui.click(mine)
        assert gui.exploded == mine


class TestRendering:
    def draw(self, screen, fonts):
        surface = pygame.Surface(screen.size)
        screen.draw(surface, fonts)
        return surface

    @pytest.mark.parametrize("mode", sorted(MODE_LABELS))
    def test_draw_all_game_phases_in_every_mode(self, mode, fonts):
        screen = GameScreen(mode, "easy")
        self.draw(screen, fonts)  # fresh board
        first = next(iter(screen.centers))
        screen.handle_event(mouse_event(screen.centers[first]))
        flag_target = next(
            cell
            for cell in screen.game.cells
            if screen.game.cell_state(cell) is CellState.HIDDEN
        )
        screen.handle_event(mouse_event(screen.centers[flag_target], button=3))
        self.draw(screen, fonts)  # mid-game with reveals and a flag
        screen.game.toggle_flag(flag_target)
        screen.click(find_mine(screen))
        assert screen.game.state is GameState.LOST
        self.draw(screen, fonts)  # loss screen with mines shown

    def test_exploded_mine_drawn_highlighted(self, gui, fonts):
        gui.handle_event(mouse_event(gui.centers[(4, 4)]))
        mine = find_mine(gui)
        gui.click(mine)
        surface = self.draw(gui, fonts)
        xs = [x for x, _ in gui.polygons[mine]]
        ys = [y for _, y in gui.polygons[mine]]
        samples = {
            surface.get_at((int(x), int(y)))[:3]
            for x in range(int(min(xs)) + 2, int(max(xs)) - 1, 3)
            for y in range(int(min(ys)) + 2, int(max(ys)) - 1, 3)
            if point_in_polygon((x, y), gui.polygons[mine])
        }
        assert EXPLODED_FACE in samples

    def test_won_game_draws(self, gui, fonts):
        gui.game = Game(gui.board.adjacency, mine_positions={(0, 0)})
        for cell in gui.game.cells:
            if cell != (0, 0):
                gui.game.reveal(cell)
        assert gui.game.state is GameState.WON
        self.draw(gui, fonts)


class TestMenu:
    def test_menu_lists_all_modes(self):
        menu = MenuScreen()
        assert {mode for _, mode in menu.mode_buttons} == set(MODE_LABELS)

    def test_clicking_a_mode_starts_it(self):
        menu = MenuScreen()
        for rect, mode in menu.mode_buttons:
            assert menu.handle_event(mouse_event(rect.center)) == ("start", mode)

    def test_clicking_difficulty_selects_it(self):
        menu = MenuScreen()
        for rect, difficulty in menu.difficulty_buttons:
            assert menu.handle_event(mouse_event(rect.center)) is None
            assert menu.difficulty == difficulty

    def test_difficulty_keys(self):
        menu = MenuScreen()
        menu.handle_event(key_event(pygame.K_3))
        assert menu.difficulty == "hard"

    def test_escape_quits_from_menu(self):
        menu = MenuScreen()
        assert menu.handle_event(key_event(pygame.K_ESCAPE)) == "quit"
        assert menu.handle_event(pygame.event.Event(pygame.QUIT)) == "quit"

    def test_empty_click_does_nothing(self):
        menu = MenuScreen()
        assert menu.handle_event(mouse_event((2, 2))) is None

    def test_menu_draws(self, fonts):
        menu = MenuScreen()
        surface = pygame.Surface(menu.size)
        menu.draw(surface, fonts)
