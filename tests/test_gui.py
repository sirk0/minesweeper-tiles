import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from minesweeper.boards import (  # noqa: E402
    APERIODIC_MODES,
    FAMILY_MEMBERS,
    MANIFOLD_ORDER,
    MENU_ROOT,
    MODE_LABELS,
    MODES_3D,
    OTHER_MODES,
    SHAPED_MODES,
    SPHERE_MODES,
    TILINGS,
    picker_modes,
)
from minesweeper.game import CellState, Game, GameState  # noqa: E402
from minesweeper.gui import (  # noqa: E402
    EXPLODED_FACE,
    FontCache,
    GameScreen,
    GameScreen3D,
    MenuScreen,
    make_icon,
    make_screen,
    point_in_polygon,
)

MODES_2D = sorted(set(MODE_LABELS) - MODES_3D)


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


def wheel_event(y):
    return pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=y, precise_x=0.0,
                              precise_y=float(y), flipped=False)


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
    @pytest.mark.parametrize("mode", MODES_2D)
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

    @pytest.mark.parametrize("mode", MODES_2D)
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

    @pytest.mark.parametrize("mode", MODES_2D)
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


class Test3DScreens:
    def nearest_visible(self, screen):
        """(cell, screen position) of the cell nearest the viewer."""
        frame = screen._project()
        _, cell, _, center, _, _ = frame[-1]
        return cell, (int(center[0]), int(center[1]))

    @pytest.mark.parametrize("mode", sorted(MODES_3D))
    def test_make_screen_selects_3d(self, mode):
        assert isinstance(make_screen(mode, "easy"), GameScreen3D)
        assert isinstance(make_screen("square", "easy"), GameScreen)

    @pytest.mark.parametrize("mode", sorted(MODES_3D))
    def test_nearest_cell_center_picks_that_cell(self, mode):
        screen = GameScreen3D(mode, "easy")
        cell, pos = self.nearest_visible(screen)
        assert screen.cell_at(pos) == cell

    @pytest.mark.parametrize("mode", sorted(MODES_3D))
    def test_short_click_reveals(self, mode):
        screen = GameScreen3D(mode, "easy")
        cell, pos = self.nearest_visible(screen)
        screen.handle_event(mouse_event(pos))  # button down
        screen.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)
        )
        assert screen.game.cell_state(cell) is CellState.REVEALED
        assert screen.game.state is not GameState.LOST  # first click safe

    @pytest.mark.parametrize("mode", sorted(MODES_3D))
    def test_drag_rotates_without_revealing(self, mode):
        screen = GameScreen3D(mode, "easy")
        initial_rotation = screen.rotation
        cell, pos = self.nearest_visible(screen)
        screen.handle_event(mouse_event(pos))
        screen.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=(pos[0] + 40, pos[1]),
                rel=(40, 0),
                buttons=(1, 0, 0),
            )
        )
        screen.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONUP, pos=(pos[0] + 40, pos[1]), button=1
            )
        )
        assert screen.rotation != initial_rotation
        assert all(
            screen.game.cell_state(c) is CellState.HIDDEN for c in screen.game.cells
        )

    def test_rotation_changes_visible_set(self):
        screen = GameScreen3D("torus", "easy")
        before = {cell for _, cell, *_ in screen._project()}
        screen.rotate(200, 0)
        after = {cell for _, cell, *_ in screen._project()}
        assert before != after

    def test_arrow_keys_rotate(self):
        screen = GameScreen3D("sphere", "easy")
        start = screen.rotation
        screen.handle_event(key_event(pygame.K_LEFT))
        assert screen.rotation != start

    @pytest.mark.parametrize("mode", sorted(MODES_3D))
    def test_right_click_flags(self, mode):
        screen = GameScreen3D(mode, "easy")
        cell, pos = self.nearest_visible(screen)
        screen.handle_event(mouse_event(pos, button=3))
        assert screen.game.cell_state(cell) is CellState.FLAGGED

    def test_backface_culled(self):
        screen = GameScreen3D("sphere", "easy")
        visible = {cell for _, cell, *_ in screen._project()}
        assert 0 < len(visible) < len(screen.game.cells)

    @pytest.mark.parametrize("mode", sorted(MODES_3D))
    def test_draw_all_game_phases(self, mode, fonts):
        screen = GameScreen3D(mode, "easy")
        surface = pygame.Surface(screen.size)
        screen.draw(surface, fonts)  # fresh board
        mine, flagged = list(screen.game.cells)[:2]
        screen.game = Game(screen.board.adjacency, mine_positions={mine})
        screen.game.toggle_flag(flagged)
        screen.draw(surface, fonts)  # mid-game with a flag
        screen.game.toggle_flag(flagged)
        screen.click(mine)
        assert screen.game.state is GameState.LOST
        screen.draw(surface, fonts)  # loss

    def test_face_click_restarts_without_dragging(self):
        screen = GameScreen3D("sphere", "easy")
        cell, _ = self.nearest_visible(screen)
        screen.click(cell)
        old_game = screen.game
        screen.handle_event(mouse_event(screen.face_rect.center))
        assert screen.game is not old_game
        assert screen._drag_from is None

    def test_scroll_shifts_cells_along_the_ring(self):
        # the Klein bottle carries a cell_cycle, so scrolling remaps which
        # game cell each face shows (geometry untouched)
        screen = GameScreen3D("klein", "easy")
        cycle = screen.board.cell_cycle
        assert screen._remap == {c: c for c in screen.board.polygons}
        screen.handle_event(wheel_event(2))
        assert screen._remap == {g: cycle[cycle[g]] for g in cycle}
        screen.handle_event(wheel_event(-2))  # back to identity
        assert screen._remap == {c: c for c in screen.board.polygons}

    def test_scroll_moves_the_clicked_cell(self):
        # after scrolling, clicking a face acts on the shifted game cell --
        # the one whose number is drawn there
        screen = GameScreen3D("klein", "easy")
        cell, pos = self.nearest_visible(screen)
        screen.handle_event(wheel_event(1))
        expected = screen.board.cell_cycle[cell]
        screen.handle_event(mouse_event(pos, button=3))
        assert screen.game.cell_state(expected) is CellState.FLAGGED
        assert screen.game.cell_state(cell) is CellState.HIDDEN

    def test_non_klein_board_ignores_scroll(self):
        screen = GameScreen3D("torus", "easy")
        assert screen.board.cell_cycle is None
        screen.handle_event(wheel_event(3))
        assert screen._remap == {c: c for c in screen.board.polygons}


class TestMenu:
    def items(self, menu):
        return {key for _, key, _, _ in menu.layout()["items"]}

    def click_item(self, menu, wanted):
        for rect, key, _, _ in menu.layout()["items"]:
            if key == wanted:
                return menu.handle_event(mouse_event(rect.center))
        raise AssertionError(f"{wanted} not on the current page")

    def test_home_page_lists_the_five_entries(self):
        menu = MenuScreen()
        assert menu.path == []
        assert self.items(menu) == set(MENU_ROOT)
        assert menu.layout()["back"] is None

    def test_classic_launches_flat_squares(self):
        menu = MenuScreen()
        assert self.click_item(menu, "classic") == ("start", "square")

    # -- Flat: the tiling picker on the plane -------------------------------

    def test_flat_opens_the_tiling_picker(self):
        menu = MenuScreen()
        assert self.click_item(menu, "flat") is None
        assert menu.path == ["flat"]
        assert self.items(menu) == {
            "square", "tri", "hex", "uniform", "dual", "aperiodic", "random"
        }

    def test_flat_regular_tiling_launches_at_once(self):
        menu = MenuScreen()
        self.click_item(menu, "flat")
        assert self.click_item(menu, "hex") == ("start", "hex")

    def test_flat_uniform_family_reaches_a_tiling(self):
        menu = MenuScreen()
        self.click_item(menu, "flat")
        self.click_item(menu, "uniform")
        assert self.items(menu) == set(FAMILY_MEMBERS["uniform"])
        assert self.click_item(menu, "kagome") == ("start", "kagome")

    def test_flat_dual_family_reaches_a_laves_tiling(self):
        menu = MenuScreen()
        self.click_item(menu, "flat")
        self.click_item(menu, "dual")
        assert self.items(menu) == set(FAMILY_MEMBERS["dual"])
        assert self.click_item(menu, "rhombille") == ("start", "rhombille")

    def test_flat_aperiodic_family_launches_a_mode(self):
        menu = MenuScreen()
        self.click_item(menu, "flat")
        self.click_item(menu, "aperiodic")
        assert self.items(menu) == set(APERIODIC_MODES)
        assert self.click_item(menu, "penrose") == ("start", "penrose")

    def test_flat_random_tiling_launches_a_flat_board(self):
        menu = MenuScreen()
        self.click_item(menu, "flat")
        result = self.click_item(menu, "random")
        assert result[0] == "start" and result[1] in picker_modes("flat")

    # -- Flat manifolds -----------------------------------------------------

    def test_manifolds_lists_the_surfaces(self):
        menu = MenuScreen()
        assert self.click_item(menu, "manifolds") is None
        assert self.items(menu) == set(MANIFOLD_ORDER)

    def test_manifold_opens_a_picker_and_wraps_a_tiling(self):
        menu = MenuScreen()
        self.click_item(menu, "manifolds")
        self.click_item(menu, "torus")
        assert menu.path == ["manifolds", "torus"]
        # aperiodic is not offered on a wrapped surface, only on the plane
        assert self.items(menu) == {
            "square", "tri", "hex", "uniform", "dual", "random"
        }
        self.click_item(menu, "uniform")
        assert self.click_item(menu, "kagome") == ("start", "toruskagome")

    def test_manifold_regular_tiling_wraps(self):
        menu = MenuScreen()
        self.click_item(menu, "manifolds")
        self.click_item(menu, "cylinder")
        assert self.click_item(menu, "tri") == ("start", "cyltri")

    def test_manifold_random_draws_from_that_surface(self):
        menu = MenuScreen()
        self.click_item(menu, "manifolds")
        self.click_item(menu, "klein")
        result = self.click_item(menu, "random")
        assert result[0] == "start" and result[1] in picker_modes("klein")

    # -- Sphere and Other ---------------------------------------------------

    def test_sphere_lists_spherical_tilings(self):
        menu = MenuScreen()
        self.click_item(menu, "sphere")
        assert self.items(menu) == set(SPHERE_MODES)
        assert self.click_item(menu, "spheretri") == ("start", "spheretri")

    def test_other_lists_solids_and_a_shaped_submenu(self):
        menu = MenuScreen()
        self.click_item(menu, "other")
        assert self.items(menu) == set(OTHER_MODES) | {"shaped"}
        assert self.click_item(menu, "cubeframe") == ("start", "cubeframe")

    def test_other_shaped_lists_its_boards(self):
        menu = MenuScreen()
        self.click_item(menu, "other")
        self.click_item(menu, "shaped")
        assert self.items(menu) == set(SHAPED_MODES)
        assert self.click_item(menu, "hexhex") == ("start", "hexhex")

    # -- reachability & gating ---------------------------------------------

    def test_every_mode_is_reachable(self):
        reached = set()

        def reach(*clicks):
            menu = MenuScreen()
            result = None
            for key in clicks:
                result = self.click_item(menu, key)
            assert result[0] == "start"
            reached.add(result[1])

        reach("classic")
        # the tiling picker on the plane and on every flat manifold
        for surface_path in (["flat"], ["manifolds", "cylinder"],
                             ["manifolds", "mobius"], ["manifolds", "klein"],
                             ["manifolds", "torus"]):
            for tiling in ("square", "tri", "hex"):
                reach(*surface_path, tiling)
            for family in ("uniform", "dual"):
                menu = MenuScreen()
                for key in surface_path + [family]:
                    self.click_item(menu, key)
                for _, key, _, enabled in menu.layout()["items"]:
                    if enabled:  # chiral tilings are gated out per surface
                        reach(*surface_path, family, key)
        for mode in APERIODIC_MODES:  # aperiodic wraps only the plane
            reach("flat", "aperiodic", mode)
        for mode in SPHERE_MODES:
            reach("sphere", mode)
        for mode in OTHER_MODES:
            reach("other", mode)
        for mode in SHAPED_MODES:
            reach("other", "shaped", mode)
        assert reached == set(MODE_LABELS)

    def test_chiral_tiling_disabled_on_a_mirror_surface(self):
        # snub hexagonal is chiral, so it cannot wrap the Möbius strip or the
        # Klein bottle; it shows disabled in the picker on those surfaces
        for surface in ("mobius", "klein"):
            menu = MenuScreen()
            self.click_item(menu, "manifolds")
            self.click_item(menu, surface)
            self.click_item(menu, "uniform")
            enabled = {key: on for _, key, _, on in menu.layout()["items"]}
            assert enabled["snubhex"] is False
            assert enabled["kagome"] is True
            assert self.click_item(menu, "snubhex") is None  # click ignored
            assert menu.path == ["manifolds", surface, "uniform"]

    def test_chiral_dual_disabled_on_a_mirror_surface(self):
        # the floret pentagonal (dual of snub hexagonal) is chiral too
        menu = MenuScreen()
        self.click_item(menu, "manifolds")
        self.click_item(menu, "mobius")
        self.click_item(menu, "dual")
        enabled = {key: on for _, key, _, on in menu.layout()["items"]}
        assert enabled["floret"] is False
        assert enabled["rhombille"] is True

    def test_back_button_pops_one_page(self):
        menu = MenuScreen()
        self.click_item(menu, "manifolds")
        self.click_item(menu, "torus")
        self.click_item(menu, "uniform")
        back = menu.layout()["back"]
        assert menu.handle_event(mouse_event(back.center)) is None
        assert menu.path == ["manifolds", "torus"]
        assert menu.handle_event(mouse_event(back.center)) is None
        assert menu.path == ["manifolds"]
        assert menu.handle_event(mouse_event(back.center)) is None
        assert menu.path == []

    def test_escape_goes_back_then_quits(self):
        menu = MenuScreen()
        self.click_item(menu, "flat")
        self.click_item(menu, "uniform")
        assert menu.handle_event(key_event(pygame.K_ESCAPE)) is None
        assert menu.path == ["flat"]
        assert menu.handle_event(key_event(pygame.K_ESCAPE)) is None
        assert menu.path == []
        assert menu.handle_event(key_event(pygame.K_ESCAPE)) == "quit"
        assert menu.handle_event(pygame.event.Event(pygame.QUIT)) == "quit"

    def test_clicking_difficulty_selects_it(self):
        menu = MenuScreen()
        for rect, difficulty in menu.layout()["difficulty"]:
            assert menu.handle_event(mouse_event(rect.center)) is None
            assert menu.difficulty == difficulty

    def test_difficulty_keys(self):
        menu = MenuScreen()
        menu.handle_event(key_event(pygame.K_3))
        assert menu.difficulty == "hard"

    def test_empty_click_does_nothing(self):
        menu = MenuScreen()
        assert menu.handle_event(mouse_event((2, 2))) is None

    def test_all_pages_draw(self, fonts):
        menu = MenuScreen()
        for path in ([], ["flat"], ["flat", "uniform"], ["flat", "aperiodic"],
                     ["manifolds"], ["manifolds", "klein"],
                     ["manifolds", "klein", "uniform"],
                     ["manifolds", "mobius", "dual"],
                     ["sphere"], ["other"], ["other", "shaped"]):
            menu.path = list(path)
            surface = pygame.Surface(menu.size)
            menu.draw(surface, fonts)


class TestIcon:
    def test_app_icon_is_high_resolution(self):
        icon = make_icon()
        assert icon.get_size() == (512, 512)
        # opaque in the middle (the mine), transparent at the corners
        # (macOS-style rounded plate with a margin)
        assert icon.get_at((256, 256))[3] == 255
        assert icon.get_at((2, 2))[3] == 0

    def test_bleed_icon_fills_corners_for_ios(self):
        # the iOS home-screen icon is full-bleed and opaque to its edges so
        # iOS's own rounded-square mask makes it match the macOS dock icon
        icon = make_icon(180, bleed=True)
        assert icon.get_size() == (180, 180)
        assert icon.get_at((90, 90))[3] == 255
        assert icon.get_at((0, 0))[3] == 255

    def test_menu_icons_render_for_every_menu_key(self):
        from minesweeper.gui import ICON_SIZE, menu_icon

        keys = (
            set(MENU_ROOT)                       # home entries
            | {"random", "shaped"}               # picker / other submenu rows
            | set(MANIFOLD_ORDER)                # the flat-manifold surfaces
            | {"uniform", "dual", "aperiodic"}   # tiling families
            | set(TILINGS)                       # every tiling row in the picker
            | set(SPHERE_MODES)
            | set(OTHER_MODES)
            | set(SHAPED_MODES)
            | set(APERIODIC_MODES)
        )
        for key in sorted(keys):
            icon = menu_icon(key)
            assert icon.get_size() == (ICON_SIZE, ICON_SIZE)
            opaque = any(
                icon.get_at((x, y))[3] > 0
                for x in range(0, ICON_SIZE, 6)
                for y in range(0, ICON_SIZE, 6)
            )
            assert opaque, key


class TestHeaderMenuButton:
    def test_menu_button_returns_menu_2d(self):
        screen = GameScreen("square", "easy")
        event = mouse_event(screen.menu_rect.center)
        assert screen.handle_event(event) == "menu"

    def test_menu_button_returns_menu_3d(self):
        screen = GameScreen3D("sphere", "easy")
        event = mouse_event(screen.menu_rect.center)
        assert screen.handle_event(event) == "menu"
        assert screen._drag_from is None  # click did not start a drag


class TestDragDirection:
    def test_vertical_drag_is_inverted(self):
        dragged = GameScreen3D("sphere", "easy")
        reference = GameScreen3D("sphere", "easy")
        pos = (200, 300)
        dragged.handle_event(mouse_event(pos))
        dragged.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=(pos[0], pos[1] + 40),
                rel=(0, 40),
                buttons=(1, 0, 0),
            )
        )
        # dragging down by 40 px must equal rotate(0, -40)
        reference.rotate(0, -40)
        assert dragged.rotation == reference.rotation
