"""Pygame GUI for minesweeper.

Run with ``python -m minesweeper``. A menu screen selects the board
mode (squares, triangles, hexagons, or the 3D sphere/donut) and
difficulty. In game: left-click reveals (on a revealed number: chords),
right-click flags, the face button or ``n`` restarts, ``1``/``2``/``3``
switch difficulty, ``Escape`` returns to the menu. On 3D boards, drag
with the left button (or use the arrow keys) to rotate the surface.
"""

from __future__ import annotations

import argparse
import math
import sys
import time

import pygame

from minesweeper.boards import (
    DIFFICULTIES,
    MODE_LABELS,
    MODES_3D,
    build_board,
    newell_normal,
)
from minesweeper.game import CellState, Game, GameState

MARGIN = 8
HEADER = 52

BG = (192, 192, 192)
BEVEL_LIGHT = (255, 255, 255)
BEVEL_DARK = (110, 110, 110)
HIDDEN_FACE = (172, 172, 172)
REVEALED_FACE = (225, 225, 225)
EXPLODED_FACE = (255, 80, 80)
GRID_LINE = (130, 130, 130)
COUNTER_BG = (40, 0, 0)
COUNTER_FG = (255, 40, 40)
TEXT = (30, 30, 30)
SELECTED = (120, 160, 220)

NUMBER_COLORS = {
    1: (0, 0, 255),
    2: (0, 128, 0),
    3: (255, 0, 0),
    4: (0, 0, 128),
    5: (128, 0, 0),
    6: (0, 128, 128),
    7: (0, 0, 0),
    8: (96, 96, 96),
    9: (128, 0, 128),
    10: (200, 100, 0),
    11: (180, 0, 90),
    12: (60, 60, 60),
}

FACES = {"playing": ":)", "won": "B)", "lost": "X("}

DIFFICULTY_KEYS = {pygame.K_1: "easy", pygame.K_2: "medium", pygame.K_3: "hard"}

DRAG_THRESHOLD = 5  # pixels of motion that turn a click into a rotation drag


# -- geometry helpers -------------------------------------------------------


def centroid(vertices: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(vertices)
    return (sum(x for x, _ in vertices) / n, sum(y for _, y in vertices) / n)


def _dist_point_segment(p, a, b) -> float:
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(
        0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq)
    )
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def inradius(vertices: list[tuple[float, float]]) -> float:
    """Distance from the centroid to the nearest edge — how big a glyph
    fits inside the cell."""
    center = centroid(vertices)
    n = len(vertices)
    return min(
        _dist_point_segment(center, vertices[i], vertices[(i + 1) % n])
        for i in range(n)
    )


def point_in_polygon(point: tuple[float, float], vertices) -> bool:
    x, y = point
    inside = False
    j = len(vertices) - 1
    for i in range(len(vertices)):
        xi, yi = vertices[i]
        xj, yj = vertices[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


# -- 3D math -----------------------------------------------------------------


IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def rot_x(angle: float):
    c, s = math.cos(angle), math.sin(angle)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def rot_y(angle: float):
    c, s = math.cos(angle), math.sin(angle)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def mat_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def mat_apply(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


class FontCache:
    FAMILY = "menlo, couriernew, monospace"

    def __init__(self) -> None:
        pygame.font.init()
        self._fonts: dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        if size not in self._fonts:
            self._fonts[size] = pygame.font.SysFont(self.FAMILY, size, bold=True)
        return self._fonts[size]


# -- glyphs ------------------------------------------------------------------


def draw_mine(surface, center, radius) -> None:
    cx, cy = int(center[0]), int(center[1])
    pygame.draw.circle(surface, (0, 0, 0), (cx, cy), max(3, int(radius * 0.5)))
    spike = radius * 0.85
    for dx, dy in ((1, 0), (0, 1), (0.7, 0.7), (0.7, -0.7)):
        start = (cx - dx * spike, cy - dy * spike)
        end = (cx + dx * spike, cy + dy * spike)
        pygame.draw.line(surface, (0, 0, 0), start, end, 2)


def draw_flag(surface, center, radius, *, wrong: bool) -> None:
    cx, cy = center
    top, bottom = cy - radius * 0.9, cy + radius * 0.9
    pygame.draw.line(surface, (0, 0, 0), (cx, top), (cx, bottom), 2)
    pygame.draw.polygon(
        surface,
        (255, 0, 0),
        [(cx, top), (cx - radius * 0.9, top + radius * 0.45), (cx, top + radius * 0.9)],
    )
    if wrong:  # misplaced flag revealed at game end
        r = radius * 0.95
        pygame.draw.line(surface, (0, 0, 0), (cx - r, cy - r), (cx + r, cy + r), 2)
        pygame.draw.line(surface, (0, 0, 0), (cx - r, cy + r), (cx + r, cy - r), 2)


def _bevel_button(surface, rect) -> None:
    pygame.draw.rect(surface, HIDDEN_FACE, rect)
    pygame.draw.line(surface, BEVEL_LIGHT, rect.topleft, rect.topright, 2)
    pygame.draw.line(surface, BEVEL_LIGHT, rect.topleft, rect.bottomleft, 2)
    pygame.draw.line(surface, BEVEL_DARK, rect.bottomleft, rect.bottomright, 2)
    pygame.draw.line(surface, BEVEL_DARK, rect.topright, rect.bottomright, 2)


# -- game screens ------------------------------------------------------------


class BaseGameScreen:
    """Shared game lifecycle, header and input handling; subclasses supply
    geometry (cell polygons, hit testing and board drawing)."""

    def __init__(self, mode: str, difficulty: str = "easy") -> None:
        self.mode = mode
        self.difficulty = difficulty
        self.new_game()

    def new_game(self, difficulty: str | None = None) -> None:
        if difficulty is not None:
            self.difficulty = difficulty
        self.board = build_board(self.mode, self.difficulty)
        self.game = Game(self.board.adjacency, self.board.mine_count)
        self.exploded = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self._setup_geometry()

    def _setup_geometry(self) -> None:
        raise NotImplementedError

    def cell_at(self, pos):
        raise NotImplementedError

    def draw_board(self, surface, fonts: FontCache) -> None:
        raise NotImplementedError

    @property
    def size(self) -> tuple[int, int]:
        raise NotImplementedError

    @property
    def elapsed(self) -> int:
        if self.started_at is None:
            return 0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return min(999, int(end - self.started_at))

    @property
    def face_rect(self) -> pygame.Rect:
        return pygame.Rect(self.size[0] // 2 - 18, MARGIN + 4, 36, 36)

    # -- input ------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event):
        """Returns "quit", "menu", or None."""
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if event.key == pygame.K_n:
                self.new_game()
            elif event.key in DIFFICULTY_KEYS:
                self.new_game(DIFFICULTY_KEYS[event.key])
            else:
                self._handle_key(event)
        if event.type in (
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            self._handle_mouse(event)
        return None

    def _handle_key(self, event) -> None:
        pass

    def _handle_mouse(self, event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        if self.face_rect.collidepoint(event.pos):
            self.new_game()
            return
        cell = self.cell_at(event.pos)
        if cell is not None:
            if event.button == 1:
                self.click(cell)
            elif event.button == 3:
                self.game.toggle_flag(cell)

    def click(self, cell) -> None:
        """Left-click: reveal a hidden cell, chord a revealed one."""
        if self.game.state is not GameState.PLAYING:
            return
        if self.started_at is None:
            self.started_at = time.monotonic()
        if self.game.cell_state(cell) is CellState.REVEALED:
            self.game.chord(cell)
        else:
            self.game.reveal(cell)
        if self.game.state is GameState.LOST and self.exploded is None:
            self.exploded = self.find_exploded(cell)
        if self.game.state is not GameState.PLAYING:
            self.finished_at = time.monotonic()

    def find_exploded(self, cell):
        """The mine that ended the game: the clicked cell or, after a bad
        chord, whichever revealed neighbor is a mine."""
        if self.game.is_mine(cell):
            return cell
        for n in self.game.neighbors(cell):
            if self.game.is_mine(n) and self.game.cell_state(n) is CellState.REVEALED:
                return n
        return cell

    # -- drawing ----------------------------------------------------------

    def draw(self, surface: pygame.Surface, fonts: FontCache) -> None:
        surface.fill(BG)
        self.draw_header(surface, fonts)
        self.draw_board(surface, fonts)

    def draw_cell(self, surface, fonts, cell, vertices, center, glyph_radius) -> None:
        game = self.game
        state = game.cell_state(cell)
        lost = game.state is GameState.LOST
        show_mine = lost and game.is_mine(cell) and state is not CellState.FLAGGED

        if state is CellState.REVEALED or show_mine:
            face = EXPLODED_FACE if cell == self.exploded else REVEALED_FACE
            pygame.draw.polygon(surface, face, vertices)
            pygame.draw.polygon(surface, GRID_LINE, vertices, 1)
        else:
            pygame.draw.polygon(surface, HIDDEN_FACE, vertices)
            pygame.draw.polygon(surface, BEVEL_LIGHT, vertices, 2)
            pygame.draw.polygon(surface, GRID_LINE, vertices, 1)

        if show_mine:
            draw_mine(surface, center, glyph_radius)
        elif state is CellState.FLAGGED:
            wrong = lost and not game.is_mine(cell)
            draw_flag(surface, center, glyph_radius, wrong=wrong)
        elif game.state is GameState.WON and game.is_mine(cell):
            draw_flag(surface, center, glyph_radius, wrong=False)
        elif state is CellState.REVEALED:
            n = game.adjacent_mines(cell)
            if n:
                color = NUMBER_COLORS.get(n, (0, 0, 0))
                size = max(10, int(glyph_radius * 1.5))
                text = fonts.get(size).render(str(n), True, color)
                surface.blit(text, text.get_rect(center=center))

    def draw_header(self, surface, fonts: FontCache) -> None:
        width = self.size[0]

        counter = f"{max(-99, min(999, self.game.flags_remaining)):03d}"
        self.draw_counter(surface, fonts, counter, x=MARGIN + 4)

        timer = f"{self.elapsed:03d}"
        timer_width = fonts.get(24).size(timer)[0] + 12
        self.draw_counter(surface, fonts, timer, x=width - MARGIN - 4 - timer_width)

        rect = self.face_rect
        _bevel_button(surface, rect)
        face = FACES[self.game.state.value]
        text = fonts.get(16).render(face, True, (0, 0, 0))
        surface.blit(text, text.get_rect(center=rect.center))

    def draw_counter(self, surface, fonts: FontCache, value: str, *, x: int) -> None:
        text = fonts.get(24).render(value, True, COUNTER_FG)
        box = pygame.Rect(x, MARGIN + 6, text.get_width() + 12, 32)
        pygame.draw.rect(surface, COUNTER_BG, box)
        surface.blit(text, text.get_rect(center=box.center))


class GameScreen(BaseGameScreen):
    """Flat boards: static polygons straight from the board definition."""

    def _setup_geometry(self) -> None:
        offset_x, offset_y = MARGIN, MARGIN + HEADER
        self.polygons = {
            cell: [(x + offset_x, y + offset_y) for x, y in vertices]
            for cell, vertices in self.board.polygons.items()
        }
        self.centers = {
            cell: centroid(vertices) for cell, vertices in self.polygons.items()
        }
        any_cell = next(iter(self.polygons))
        self.glyph_radius = inradius(self.polygons[any_cell]) * 0.85

    @property
    def size(self) -> tuple[int, int]:
        return (
            math.ceil(self.board.width) + 2 * MARGIN,
            math.ceil(self.board.height) + HEADER + 2 * MARGIN,
        )

    def cell_at(self, pos):
        for cell, vertices in self.polygons.items():
            if point_in_polygon(pos, vertices):
                return cell
        return None

    def draw_board(self, surface, fonts: FontCache) -> None:
        for cell in self.polygons:
            self.draw_cell(
                surface, fonts, cell, self.polygons[cell],
                self.centers[cell], self.glyph_radius,
            )


class GameScreen3D(BaseGameScreen):
    """Curved boards (sphere, torus) rendered with an orthographic
    projection: back faces are culled, visible faces painted far to near.
    Dragging rotates the surface; a short click reveals."""

    VIEWPORT = 540
    ROTATE_SPEED = 0.008  # radians per pixel of drag

    def _setup_geometry(self) -> None:
        self.rotation = IDENTITY
        if self.mode == "torus":  # tilt so the tube is visible, not edge-on
            self.rotation = rot_x(-1.0)
        self.scale = (self.VIEWPORT / 2 - 24) / self.board.radius
        self._drag_from = None
        self._dragged = False
        self._frame = None  # projected geometry, rebuilt after rotation

    @property
    def size(self) -> tuple[int, int]:
        return (
            self.VIEWPORT + 2 * MARGIN,
            self.VIEWPORT + HEADER + 2 * MARGIN,
        )

    def _project(self):
        """Rotate, cull and depth-sort the cells. Returns a far-to-near
        list of (depth, cell, screen polygon, center, glyph radius)."""
        if self._frame is not None:
            return self._frame
        cx = self.size[0] / 2
        cy = MARGIN + HEADER + self.VIEWPORT / 2
        frame = []
        for cell, points in self.board.polygons.items():
            rotated = [mat_apply(self.rotation, p) for p in points]
            if newell_normal(rotated)[2] <= 0:  # facing away from the viewer
                continue
            polygon = [
                (cx + x * self.scale, cy - y * self.scale) for x, y, _ in rotated
            ]
            depth = sum(z for _, _, z in rotated) / len(rotated)
            center = centroid(polygon)
            frame.append((depth, cell, polygon, center, inradius(polygon) * 0.8))
        frame.sort(key=lambda entry: entry[0])
        self._frame = frame
        return frame

    def rotate(self, dx_pixels: float, dy_pixels: float) -> None:
        turn = mat_mul(
            rot_x(-dy_pixels * self.ROTATE_SPEED),
            rot_y(dx_pixels * self.ROTATE_SPEED),
        )
        self.rotation = mat_mul(turn, self.rotation)
        self._frame = None

    def cell_at(self, pos):
        for _, cell, polygon, _, _ in reversed(self._project()):  # near first
            if point_in_polygon(pos, polygon):
                return cell
        return None

    def _handle_key(self, event) -> None:
        step = 40  # pixels-worth of rotation per key press
        if event.key == pygame.K_LEFT:
            self.rotate(-step, 0)
        elif event.key == pygame.K_RIGHT:
            self.rotate(step, 0)
        elif event.key == pygame.K_UP:
            self.rotate(0, -step)
        elif event.key == pygame.K_DOWN:
            self.rotate(0, step)

    def _handle_mouse(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.face_rect.collidepoint(event.pos):
                    self.new_game()
                    return
                self._drag_from = event.pos
                self._dragged = False
            elif event.button == 3:
                cell = self.cell_at(event.pos)
                if cell is not None:
                    self.game.toggle_flag(cell)
        elif event.type == pygame.MOUSEMOTION and self._drag_from is not None:
            if not self._dragged:
                moved = math.hypot(
                    event.pos[0] - self._drag_from[0],
                    event.pos[1] - self._drag_from[1],
                )
                if moved < DRAG_THRESHOLD:
                    return
                self._dragged = True
            self.rotate(*event.rel)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag_from is not None and not self._dragged:
                cell = self.cell_at(event.pos)
                if cell is not None:
                    self.click(cell)
            self._drag_from = None
            self._dragged = False

    def draw_board(self, surface, fonts: FontCache) -> None:
        for _, cell, polygon, center, glyph_radius in self._project():
            self.draw_cell(surface, fonts, cell, polygon, center, glyph_radius)


def make_screen(mode: str, difficulty: str) -> BaseGameScreen:
    cls = GameScreen3D if mode in MODES_3D else GameScreen
    return cls(mode, difficulty)


# -- menu screen ---------------------------------------------------------------


class MenuScreen:
    WIDTH = 460

    def __init__(self, difficulty: str = "easy") -> None:
        self.difficulty = difficulty
        self.mode_buttons: list[tuple[pygame.Rect, str]] = []
        y = 96
        for mode in MODE_LABELS:
            self.mode_buttons.append((pygame.Rect(50, y, self.WIDTH - 100, 58), mode))
            y += 72
        y += 14
        self.difficulty_buttons: list[tuple[pygame.Rect, str]] = []
        button_width = 110
        x = (self.WIDTH - 3 * button_width - 2 * 12) // 2
        for difficulty_key in DIFFICULTIES:
            self.difficulty_buttons.append(
                (pygame.Rect(x, y, button_width, 40), difficulty_key)
            )
            x += button_width + 12
        self.height = y + 40 + 32

    @property
    def size(self) -> tuple[int, int]:
        return (self.WIDTH, self.height)

    def handle_event(self, event: pygame.event.Event):
        """Returns "quit", ("start", mode), or None."""
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "quit"
            if event.key in DIFFICULTY_KEYS:
                self.difficulty = DIFFICULTY_KEYS[event.key]
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, difficulty_key in self.difficulty_buttons:
                if rect.collidepoint(event.pos):
                    self.difficulty = difficulty_key
                    return None
            for rect, mode in self.mode_buttons:
                if rect.collidepoint(event.pos):
                    return ("start", mode)
        return None

    def draw(self, surface: pygame.Surface, fonts: FontCache) -> None:
        surface.fill(BG)
        title = fonts.get(30).render("MINESWEEPER", True, TEXT)
        surface.blit(title, title.get_rect(center=(self.WIDTH // 2, 42)))
        subtitle = fonts.get(14).render("choose a board", True, GRID_LINE)
        surface.blit(subtitle, subtitle.get_rect(center=(self.WIDTH // 2, 70)))

        for rect, mode in self.mode_buttons:
            _bevel_button(surface, rect)
            self.draw_mode_icon(surface, mode, rect)
            label = fonts.get(18).render(MODE_LABELS[mode], True, TEXT)
            surface.blit(
                label, label.get_rect(midleft=(rect.left + 64, rect.centery))
            )

        for rect, difficulty_key in self.difficulty_buttons:
            if difficulty_key == self.difficulty:
                pygame.draw.rect(surface, SELECTED, rect)
                pygame.draw.rect(surface, TEXT, rect, 2)
            else:
                _bevel_button(surface, rect)
            label = fonts.get(15).render(difficulty_key.capitalize(), True, TEXT)
            surface.blit(label, label.get_rect(center=rect.center))

    def draw_mode_icon(self, surface, mode: str, button: pygame.Rect) -> None:
        cx, cy = button.left + 34, button.centery
        color, width = TEXT, 2
        if mode == "square":
            rect = pygame.Rect(cx - 13, cy - 13, 26, 26)
            pygame.draw.rect(surface, color, rect, width)
            pygame.draw.line(surface, color, (cx, cy - 13), (cx, cy + 13), width)
            pygame.draw.line(surface, color, (cx - 13, cy), (cx + 13, cy), width)
        elif mode == "triangle":
            outer = [(cx, cy - 15), (cx - 17, cy + 13), (cx + 17, cy + 13)]
            inner = [(cx - 8.5, cy - 1), (cx + 8.5, cy - 1), (cx, cy + 13)]
            pygame.draw.polygon(surface, color, outer, width)
            pygame.draw.polygon(surface, color, inner, width)
        elif mode == "trigrid":
            for i, up in enumerate((True, False, True)):
                x = cx - 18 + i * 12
                if up:
                    points = [(x, cy + 11), (x + 24, cy + 11), (x + 12, cy - 11)]
                else:
                    points = [(x, cy - 11), (x + 24, cy - 11), (x + 12, cy + 11)]
                pygame.draw.polygon(surface, color, points, width)
        elif mode == "hex":
            points = [
                (cx + 15 * math.cos(math.radians(60 * k + 30)),
                 cy + 15 * math.sin(math.radians(60 * k + 30)))
                for k in range(6)
            ]
            pygame.draw.polygon(surface, color, points, width)
        elif mode == "sphere":
            pygame.draw.circle(surface, color, (cx, cy), 15, width)
            points = [
                (cx + 8 * math.cos(math.radians(72 * k - 90)),
                 cy + 8 * math.sin(math.radians(72 * k - 90)))
                for k in range(5)
            ]
            pygame.draw.polygon(surface, color, points, width)
        elif mode == "torus":
            pygame.draw.ellipse(surface, color, pygame.Rect(cx - 16, cy - 10, 32, 20), width)
            pygame.draw.ellipse(surface, color, pygame.Rect(cx - 6, cy - 4, 12, 8), width)


# -- application -------------------------------------------------------------


class App:
    def __init__(self, mode: str | None = None, difficulty: str = "easy") -> None:
        self.menu = MenuScreen(difficulty)
        self.screen = (
            make_screen(mode, difficulty) if mode is not None else self.menu
        )

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Minesweeper")
        window = pygame.display.set_mode(self.screen.size)
        fonts = FontCache()
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                result = self.screen.handle_event(event)
                if result == "quit":
                    running = False
                    break
                if result == "menu":
                    self.menu.difficulty = self.screen.difficulty
                    self.screen = self.menu
                elif isinstance(result, tuple) and result[0] == "start":
                    self.screen = make_screen(result[1], self.menu.difficulty)
            if not running:
                break
            if window.get_size() != self.screen.size:
                window = pygame.display.set_mode(self.screen.size)
            self.screen.draw(window, fonts)
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minesweeper", description=__doc__)
    parser.add_argument(
        "--mode",
        choices=sorted(MODE_LABELS),
        help="skip the menu and start this board mode",
    )
    parser.add_argument(
        "difficulty",
        nargs="?",
        choices=sorted(DIFFICULTIES),
        default="easy",
        help="board preset (default: easy)",
    )
    args = parser.parse_args(argv)
    App(args.mode, args.difficulty).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
