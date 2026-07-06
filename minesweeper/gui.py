"""Pygame GUI for minesweeper.

Run with ``python -m minesweeper``. The menu picks a topology (flat,
sphere, donut, Möbius strip, cylinder), then a tiling and difficulty.
In game: left-click reveals (on a revealed number: chords), right-click
flags, the face button or ``n`` restarts, ``1``/``2``/``3`` switch
difficulty, ``Escape`` goes back. On 3D boards, drag with the left
button (or use the arrow keys) to rotate the surface.
"""

from __future__ import annotations

import argparse
import math
import sys
import time

import pygame
import pygame.gfxdraw

from minesweeper.boards import (
    DIFFICULTIES,
    MODE_LABELS,
    MODES_3D,
    TOPOLOGIES,
    build_board,
    newell_normal,
)
from minesweeper.game import CellState, Game, GameState

MARGIN = 10
HEADER = 56

# modern dark palette
BG = (26, 28, 35)
HIDDEN_FACE = (86, 98, 132)
REVEALED_FACE = (44, 48, 59)
EXPLODED_FACE = (226, 67, 67)
PANEL = (17, 18, 23)
COUNTER_FG = (255, 99, 99)
TEXT = (232, 235, 242)
MUTED = (138, 146, 164)
BUTTON = (46, 51, 64)
BUTTON_HOVER = (62, 69, 86)
ACCENT = (91, 140, 255)
FLAG_COLOR = (255, 107, 107)
MINE_COLOR = (216, 221, 232)
FACE_YELLOW = (255, 202, 76)

NUMBER_COLORS = {
    1: (100, 181, 246),
    2: (129, 199, 132),
    3: (229, 115, 115),
    4: (186, 104, 200),
    5: (255, 183, 77),
    6: (77, 208, 225),
    7: (240, 98, 146),
    8: (207, 216, 220),
    9: (255, 138, 101),
    10: (174, 213, 129),
    11: (149, 117, 205),
    12: (224, 224, 224),
}

DIFFICULTY_KEYS = {pygame.K_1: "easy", pygame.K_2: "medium", pygame.K_3: "hard"}

DRAG_THRESHOLD = 5  # pixels of motion that turn a click into a rotation drag

LIGHT = (0.37, 0.46, 0.81)  # normalized light direction for 3D shading

CELL_GAP = 0.92  # cells are drawn slightly shrunk so seams show the background


# -- geometry helpers -------------------------------------------------------


def centroid(vertices: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(vertices)
    return (sum(x for x, _ in vertices) / n, sum(y for _, y in vertices) / n)


def shrink_polygon(vertices, factor: float = CELL_GAP):
    cx, cy = centroid(vertices)
    return [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in vertices]


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


def fill_polygon(surface, vertices, color) -> None:
    """Filled polygon with antialiased edges."""
    points = [(int(x), int(y)) for x, y in vertices]
    pygame.gfxdraw.filled_polygon(surface, points, color)
    pygame.gfxdraw.aapolygon(surface, points, color)


def scale_color(color, factor: float):
    return tuple(min(255, int(c * factor)) for c in color)


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
    r = max(3, int(radius * 0.5))
    spike = radius * 0.85
    for dx, dy in ((1, 0), (0, 1), (0.7, 0.7), (0.7, -0.7)):
        start = (cx - dx * spike, cy - dy * spike)
        end = (cx + dx * spike, cy + dy * spike)
        pygame.draw.line(surface, MINE_COLOR, start, end, 2)
    pygame.gfxdraw.filled_circle(surface, cx, cy, r, MINE_COLOR)
    pygame.gfxdraw.aacircle(surface, cx, cy, r, MINE_COLOR)
    glint = max(1, r // 3)
    pygame.gfxdraw.filled_circle(
        surface, cx - r // 3, cy - r // 3, glint, (255, 255, 255)
    )


def draw_flag(surface, center, radius, *, wrong: bool) -> None:
    cx, cy = center
    top, bottom = cy - radius * 0.9, cy + radius * 0.9
    pygame.draw.line(surface, TEXT, (cx, top), (cx, bottom), 2)
    fill_polygon(
        surface,
        [(cx, top), (cx - radius * 0.9, top + radius * 0.45), (cx, top + radius * 0.9)],
        FLAG_COLOR,
    )
    if wrong:  # misplaced flag revealed at game end
        r = radius * 0.95
        pygame.draw.line(surface, EXPLODED_FACE, (cx - r, cy - r), (cx + r, cy + r), 3)
        pygame.draw.line(surface, EXPLODED_FACE, (cx - r, cy + r), (cx + r, cy - r), 3)


def draw_smiley(surface, center, radius: int, state: GameState) -> None:
    cx, cy = int(center[0]), int(center[1])
    pygame.gfxdraw.filled_circle(surface, cx, cy, radius, FACE_YELLOW)
    pygame.gfxdraw.aacircle(surface, cx, cy, radius, FACE_YELLOW)
    dark = (60, 46, 12)
    eye_dx, eye_y = int(radius * 0.38), cy - int(radius * 0.25)
    if state is GameState.LOST:
        for ex in (cx - eye_dx, cx + eye_dx):
            e = max(2, radius // 5)
            pygame.draw.line(surface, dark, (ex - e, eye_y - e), (ex + e, eye_y + e), 2)
            pygame.draw.line(surface, dark, (ex - e, eye_y + e), (ex + e, eye_y - e), 2)
        mouth = pygame.Rect(0, 0, radius, int(radius * 0.7))
        mouth.center = (cx, cy + int(radius * 0.62))
        pygame.draw.arc(surface, dark, mouth, math.radians(35), math.radians(145), 2)
    else:
        if state is GameState.WON:  # sunglasses
            glass = max(3, radius // 3)
            for ex in (cx - eye_dx, cx + eye_dx):
                pygame.draw.rect(
                    surface, dark,
                    pygame.Rect(ex - glass // 2 - 1, eye_y - 2, glass + 2, glass),
                    border_radius=2,
                )
            pygame.draw.line(
                surface, dark,
                (cx - eye_dx - glass, eye_y - 1), (cx + eye_dx + glass, eye_y - 1), 2,
            )
        else:
            for ex in (cx - eye_dx, cx + eye_dx):
                pygame.gfxdraw.filled_circle(
                    surface, ex, eye_y, max(2, radius // 6), dark
                )
        mouth = pygame.Rect(0, 0, radius, int(radius * 0.8))
        mouth.center = (cx, cy + int(radius * 0.1))
        pygame.draw.arc(surface, dark, mouth, math.radians(215), math.radians(325), 2)


def make_icon(size: int = 64) -> pygame.Surface:
    """App icon: a mine inside a hexagon."""
    icon = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    r = size * 0.47
    hexagon = [
        (cx + r * math.cos(math.radians(60 * k - 90)),
         cy + r * math.sin(math.radians(60 * k - 90)))
        for k in range(6)
    ]
    fill_polygon(icon, hexagon, ACCENT)
    body = int(size * 0.2)
    spike = size * 0.33
    for dx, dy in ((1, 0), (0, 1), (0.7, 0.7), (0.7, -0.7)):
        start = (cx - dx * spike, cy - dy * spike)
        end = (cx + dx * spike, cy + dy * spike)
        pygame.draw.line(icon, PANEL, start, end, max(2, size // 20))
    pygame.gfxdraw.filled_circle(icon, cx, cy, body, PANEL)
    pygame.gfxdraw.aacircle(icon, cx, cy, body, PANEL)
    glint = max(2, body // 3)
    pygame.gfxdraw.filled_circle(
        icon, cx - body // 3, cy - body // 3, glint, (255, 255, 255)
    )
    return icon


def _button(surface, rect, *, hover: bool = False, selected: bool = False) -> None:
    color = ACCENT if selected else (BUTTON_HOVER if hover else BUTTON)
    pygame.draw.rect(surface, color, rect, border_radius=10)


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
        return pygame.Rect(self.size[0] // 2 - 20, MARGIN + 2, 40, 40)

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

    def draw_cell(
        self, surface, fonts, cell, vertices, center, glyph_radius, shade: float = 1.0
    ) -> None:
        game = self.game
        state = game.cell_state(cell)
        lost = game.state is GameState.LOST
        show_mine = lost and game.is_mine(cell) and state is not CellState.FLAGGED

        if state is CellState.REVEALED or show_mine:
            face = EXPLODED_FACE if cell == self.exploded else REVEALED_FACE
        else:
            face = HIDDEN_FACE
        fill_polygon(surface, vertices, scale_color(face, shade))

        if show_mine:
            draw_mine(surface, center, glyph_radius)
        elif state is CellState.FLAGGED:
            wrong = lost and not game.is_mine(cell)
            draw_flag(surface, center, glyph_radius, wrong=wrong)
        elif state is CellState.REVEALED:
            n = game.adjacent_mines(cell)
            if n:
                color = NUMBER_COLORS.get(n, TEXT)
                size = max(10, int(glyph_radius * 1.5))
                text = fonts.get(size).render(str(n), True, color)
                surface.blit(text, text.get_rect(center=center))

    def draw_header(self, surface, fonts: FontCache) -> None:
        width = self.size[0]

        counter = f"{max(-99, min(999, self.game.flags_remaining)):03d}"
        self.draw_counter(surface, fonts, counter, x=MARGIN)

        timer = f"{self.elapsed:03d}"
        timer_width = fonts.get(24).size(timer)[0] + 20
        self.draw_counter(surface, fonts, timer, x=width - MARGIN - timer_width)

        rect = self.face_rect
        hover = rect.collidepoint(pygame.mouse.get_pos())
        _button(surface, rect, hover=hover)
        draw_smiley(surface, rect.center, 14, self.game.state)

    def draw_counter(self, surface, fonts: FontCache, value: str, *, x: int) -> None:
        text = fonts.get(24).render(value, True, COUNTER_FG)
        box = pygame.Rect(x, MARGIN + 4, text.get_width() + 20, 36)
        pygame.draw.rect(surface, PANEL, box, border_radius=10)
        surface.blit(text, text.get_rect(center=box.center))


class GameScreen(BaseGameScreen):
    """Flat boards: static polygons straight from the board definition."""

    def _setup_geometry(self) -> None:
        offset_x, offset_y = MARGIN, MARGIN + HEADER
        self.polygons = {
            cell: [(x + offset_x, y + offset_y) for x, y in vertices]
            for cell, vertices in self.board.polygons.items()
        }
        self.display_polygons = {
            cell: shrink_polygon(vertices)
            for cell, vertices in self.polygons.items()
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
                surface, fonts, cell, self.display_polygons[cell],
                self.centers[cell], self.glyph_radius,
            )


class GameScreen3D(BaseGameScreen):
    """Curved boards rendered with an orthographic projection: faces are
    lit by a fixed light, depth-sorted and painted far to near. Closed
    surfaces cull back faces; open or one-sided surfaces (cylinder,
    Möbius strip) draw both sides. Dragging rotates; a short click
    reveals."""

    VIEWPORT = 540
    ROTATE_SPEED = 0.008  # radians per pixel of drag
    TILT = {"torus": -1.0, "mobius": -0.8, "cylinder": -0.35}

    def _setup_geometry(self) -> None:
        self.rotation = rot_x(self.TILT[self.mode]) if self.mode in self.TILT else IDENTITY
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
        """Rotate, cull, light and depth-sort the cells. Returns a
        far-to-near list of (depth, cell, polygon, center, radius, shade)."""
        if self._frame is not None:
            return self._frame
        cx = self.size[0] / 2
        cy = MARGIN + HEADER + self.VIEWPORT / 2
        two_sided = self.board.two_sided
        frame = []
        for cell, points in self.board.polygons.items():
            rotated = [mat_apply(self.rotation, p) for p in points]
            normal = newell_normal(rotated)
            length = math.hypot(*normal) or 1.0
            n = (normal[0] / length, normal[1] / length, normal[2] / length)
            if not two_sided and n[2] <= 0:  # back face of a closed surface
                continue
            light = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
            if two_sided:
                shade = 0.62 + 0.38 * abs(light)
                if n[2] < 0:
                    shade *= 0.78  # inside/back of the surface: dimmer
            else:
                shade = 0.72 + 0.28 * max(0.0, light)
            polygon = [
                (cx + x * self.scale, cy - y * self.scale) for x, y, _ in rotated
            ]
            depth = sum(z for _, _, z in rotated) / len(rotated)
            frame.append(
                (depth, cell, polygon, centroid(polygon),
                 inradius(polygon) * 0.8, shade)
            )
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
        for entry in reversed(self._project()):  # near first
            if point_in_polygon(pos, entry[2]):
                return entry[1]
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
        for _, cell, polygon, center, glyph_radius, shade in self._project():
            self.draw_cell(
                surface, fonts, cell, shrink_polygon(polygon),
                center, glyph_radius, shade,
            )


def make_screen(mode: str, difficulty: str) -> BaseGameScreen:
    cls = GameScreen3D if mode in MODES_3D else GameScreen
    return cls(mode, difficulty)


# -- menu screen ---------------------------------------------------------------


class MenuScreen:
    """Two pages: pick a topology, then one of its tilings."""

    WIDTH = 460
    ITEM_HEIGHT = 58
    ITEM_STEP = 70

    def __init__(self, difficulty: str = "easy") -> None:
        self.difficulty = difficulty
        self.topology: str | None = None  # None = topology page

    def _items(self) -> list[tuple[str, str]]:
        if self.topology is None:
            return [(key, label) for key, (label, _) in TOPOLOGIES.items()]
        _, modes = TOPOLOGIES[self.topology]
        return [(mode, MODE_LABELS[mode]) for mode in modes]

    def layout(self):
        items = self._items()
        rects = []
        y = 96
        for key, label in items:
            rects.append((pygame.Rect(50, y, self.WIDTH - 100, self.ITEM_HEIGHT), key, label))
            y += self.ITEM_STEP
        y += 14
        difficulty_buttons = []
        button_width = 110
        x = (self.WIDTH - 3 * button_width - 2 * 12) // 2
        for difficulty_key in DIFFICULTIES:
            difficulty_buttons.append(
                (pygame.Rect(x, y, button_width, 40), difficulty_key)
            )
            x += button_width + 12
        back = (
            pygame.Rect(16, 26, 84, 34) if self.topology is not None else None
        )
        return {
            "items": rects,
            "difficulty": difficulty_buttons,
            "back": back,
            "height": y + 40 + 30,
        }

    @property
    def size(self) -> tuple[int, int]:
        return (self.WIDTH, self.layout()["height"])

    def handle_event(self, event: pygame.event.Event):
        """Returns "quit", ("start", mode), or None."""
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.topology is not None:
                    self.topology = None
                    return None
                return "quit"
            if event.key in DIFFICULTY_KEYS:
                self.difficulty = DIFFICULTY_KEYS[event.key]
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            layout = self.layout()
            if layout["back"] is not None and layout["back"].collidepoint(event.pos):
                self.topology = None
                return None
            for rect, difficulty_key in layout["difficulty"]:
                if rect.collidepoint(event.pos):
                    self.difficulty = difficulty_key
                    return None
            for rect, key, _ in layout["items"]:
                if rect.collidepoint(event.pos):
                    if self.topology is None:
                        self.topology = key
                        return None
                    return ("start", key)
        return None

    def draw(self, surface: pygame.Surface, fonts: FontCache) -> None:
        surface.fill(BG)
        mouse = pygame.mouse.get_pos()
        layout = self.layout()

        title = fonts.get(30).render("MINESWEEPER", True, TEXT)
        surface.blit(title, title.get_rect(center=(self.WIDTH // 2, 44)))
        if self.topology is None:
            subtitle_text = "choose a surface"
        else:
            subtitle_text = TOPOLOGIES[self.topology][0] + " — choose a tiling"
        subtitle = fonts.get(14).render(subtitle_text, True, MUTED)
        surface.blit(subtitle, subtitle.get_rect(center=(self.WIDTH // 2, 72)))

        if layout["back"] is not None:
            rect = layout["back"]
            _button(surface, rect, hover=rect.collidepoint(mouse))
            label = fonts.get(14).render("< back", True, TEXT)
            surface.blit(label, label.get_rect(center=rect.center))

        for rect, key, label_text in layout["items"]:
            _button(surface, rect, hover=rect.collidepoint(mouse))
            draw_menu_icon(surface, key, rect)
            label = fonts.get(18).render(label_text, True, TEXT)
            surface.blit(label, label.get_rect(midleft=(rect.left + 64, rect.centery)))

        for rect, difficulty_key in layout["difficulty"]:
            selected = difficulty_key == self.difficulty
            _button(surface, rect, hover=rect.collidepoint(mouse), selected=selected)
            color = PANEL if selected else TEXT
            label = fonts.get(15).render(difficulty_key.capitalize(), True, color)
            surface.blit(label, label.get_rect(center=rect.center))


def draw_menu_icon(surface, key: str, button: pygame.Rect) -> None:
    cx, cy = button.left + 34, button.centery
    color, width = TEXT, 2
    if key in ("flat", "square", "torus_tile"):
        rect = pygame.Rect(cx - 13, cy - 13, 26, 26)
        pygame.draw.rect(surface, color, rect, width, border_radius=3)
        pygame.draw.line(surface, color, (cx, cy - 13), (cx, cy + 13), width)
        pygame.draw.line(surface, color, (cx - 13, cy), (cx + 13, cy), width)
    elif key == "triangle":
        outer = [(cx, cy - 15), (cx - 17, cy + 13), (cx + 17, cy + 13)]
        inner = [(cx - 8.5, cy - 1), (cx + 8.5, cy - 1), (cx, cy + 13)]
        pygame.draw.polygon(surface, color, outer, width)
        pygame.draw.polygon(surface, color, inner, width)
    elif key == "trigrid":
        for i, up in enumerate((True, False, True)):
            x = cx - 18 + i * 12
            if up:
                points = [(x, cy + 11), (x + 24, cy + 11), (x + 12, cy - 11)]
            else:
                points = [(x, cy - 11), (x + 24, cy - 11), (x + 12, cy + 11)]
            pygame.draw.polygon(surface, color, points, width)
    elif key == "hex":
        points = [
            (cx + 15 * math.cos(math.radians(60 * k + 30)),
             cy + 15 * math.sin(math.radians(60 * k + 30)))
            for k in range(6)
        ]
        pygame.draw.polygon(surface, color, points, width)
    elif key == "sphere":
        pygame.draw.circle(surface, color, (cx, cy), 15, width)
        points = [
            (cx + 8 * math.cos(math.radians(72 * k - 90)),
             cy + 8 * math.sin(math.radians(72 * k - 90)))
            for k in range(5)
        ]
        pygame.draw.polygon(surface, color, points, width)
    elif key in ("c60", "c80"):
        pygame.draw.circle(surface, color, (cx, cy), 15, width)
        sides = 5 if key == "c60" else 6
        points = [
            (cx - 5 + 7 * math.cos(math.radians(360 / sides * k - 90)),
             cy + 7 * math.sin(math.radians(360 / sides * k - 90)))
            for k in range(sides)
        ]
        pygame.draw.polygon(surface, color, points, width)
    elif key == "torus":
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 16, cy - 10, 32, 20), width)
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 6, cy - 4, 12, 8), width)
    elif key == "mobius":
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 16, cy - 12, 32, 24), width)
        pygame.draw.line(surface, color, (cx - 5, cy + 11), (cx + 5, cy - 11), width)
        pygame.draw.line(surface, color, (cx - 5, cy - 11), (cx + 5, cy + 11), width)
    elif key == "cylinder":
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 12, cy - 15, 24, 9), width)
        pygame.draw.line(surface, color, (cx - 12, cy - 11), (cx - 12, cy + 11), width)
        pygame.draw.line(surface, color, (cx + 12, cy - 11), (cx + 12, cy + 11), width)
        pygame.draw.arc(surface, color, pygame.Rect(cx - 12, cy + 7, 24, 9),
                        math.radians(180), math.radians(360), width)
    else:
        pygame.draw.circle(surface, color, (cx, cy), 13, width)


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
        pygame.display.set_icon(make_icon())
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
