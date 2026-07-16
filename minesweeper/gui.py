"""Pygame GUI for minesweeper.

Run with ``python -m minesweeper``. The menu picks a topology (flat,
sphere, donut, Möbius strip, cylinder), then a tiling and difficulty.
In game: left-click reveals (on a revealed number: chords), right-click
flags, the face button or ``n`` restarts, ``1``/``2``/``3`` switch
difficulty, the ``<`` button or ``Escape`` goes back to the menu. On 3D
boards, drag with the left button (or use the arrow keys) to rotate the
surface.

Rendering: the whole UI is drawn on an internal canvas at ``UI_SCALE``
times the window size and smooth-downscaled every frame (full-scene
supersampling), which antialiases polygon edges, text and glyphs.
Screens work entirely in canvas coordinates; the App scales mouse
input up to match.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import math
import os
import sys
import time

import pygame

from minesweeper.boards import (
    DIFFICULTIES,
    GROUP_TILINGS,
    GROUPS,
    MODE_LABELS,
    MODES_3D,
    SURFACE_LABELS,
    TILINGS,
    build_board,
    newell_normal,
    view_hint,
)
from minesweeper.game import CellState, Game, GameState

# pygame.gfxdraw gives antialiased primitives on the desktop but does not
# exist in the pygame wasm build (pygbag); there the browser build falls
# back to pygame.draw and relies on the full-scene supersampling for
# smoothing. importlib (not a plain import statement) keeps pygbag's
# dependency scanner from searching PyPI for "pygame.gfxdraw".
if sys.platform != "emscripten":
    importlib.import_module("pygame.gfxdraw")
_GFX = getattr(pygame, "gfxdraw", None)

UI_SCALE = 2  # supersampling factor: canvas pixels per window pixel
S = UI_SCALE

MARGIN = 10 * S
HEADER = 56 * S

# Fallback design width (in canvas pixels) for boards on the web build: the
# on-screen scale is derived from it and the window width alone -- never from
# the board currently showing -- so the UI keeps one constant size as you move
# between boards of different sizes. A board narrower than this is centred with
# background to the sides; a wider or taller one is shrunk just enough to stay
# fully visible. Each screen may override it via ``web_ref_width`` (the menu
# reports its own width so it fills the window edge to edge).
WEB_REF_WIDTH = 560 * S

# classic minesweeper grays
BG = (192, 192, 192)
HIDDEN_FACE = (189, 189, 189)
REVEALED_FACE = (205, 205, 205)
EXPLODED_FACE = (252, 84, 72)
BEVEL_LIGHT = (250, 250, 250)
BEVEL_DARK = (122, 122, 122)
GRID_LINE = (166, 166, 166)
PANEL = (24, 24, 26)
COUNTER_FG = (255, 70, 60)
TEXT = (38, 40, 44)
MUTED = (108, 112, 120)
BUTTON = (202, 202, 202)
BUTTON_HOVER = (216, 216, 216)
SELECTED = (170, 182, 202)
FLAG_COLOR = (216, 32, 32)
MINE_COLOR = (34, 36, 40)
FACE_YELLOW = (255, 202, 76)

# shiny steel blue used by the menu icons and the app icon
ICON_BLUE = (74, 120, 202)
ICON_BLUE_LIGHT = (128, 166, 230)
ICON_BLUE_DARK = (42, 76, 142)

NUMBER_COLORS = {
    1: (28, 60, 220),
    2: (30, 130, 44),
    3: (215, 34, 34),
    4: (18, 20, 144),
    5: (134, 28, 28),
    6: (36, 138, 138),
    7: (30, 30, 32),
    8: (118, 118, 122),
    9: (128, 24, 128),
    10: (190, 98, 8),
    11: (170, 20, 88),
    12: (60, 60, 64),
}

# pygame's key constants are not populated yet at import time in the wasm
# build (pygbag), so fall back to the stable SDL keycodes for 1/2/3
DIFFICULTY_KEYS = {
    getattr(pygame, "K_1", 49): "easy",
    getattr(pygame, "K_2", 50): "medium",
    getattr(pygame, "K_3", 51): "hard",
}

DRAG_THRESHOLD = 5 * S  # canvas pixels of motion that make a click a drag

LIGHT = (0.37, 0.46, 0.81)  # normalized light direction for 3D shading

TILE_LIGHT_DIR = (-0.55, -0.83)  # screen-space light for the tile bevels


# Factor that turns a window/display mouse coordinate into a canvas
# coordinate. SDL reports mouse positions in the resolution the display was
# opened at, which is not a fixed multiple of the canvas: a high-DPI desktop
# window uses logical points, and the browser build uses a device-pixel
# framebuffer sized to the page. The active presenter keeps this in sync each
# frame (see ``_DesktopPresenter`` / ``_WebPresenter``); it defaults to the
# supersampling factor so headless code and tests behave as before. The
# transform is affine -- (scale_x, scale_y, offset_x, offset_y) -- so the web
# build can letterbox the canvas inside a full-window framebuffer and still map
# clicks back to canvas coordinates.
_MOUSE_TO_CANVAS: tuple[float, float, float, float] = (float(S), float(S), 0.0, 0.0)


def canvas_mouse() -> tuple[int, int]:
    """Mouse position in canvas coordinates."""
    x, y = pygame.mouse.get_pos()
    sx, sy, ox, oy = _MOUSE_TO_CANVAS
    return (round(x * sx + ox), round(y * sy + oy))


def _set_mouse_transform(
    scale: tuple[float, float], offset: tuple[float, float] = (0.0, 0.0)
) -> None:
    """Record the affine map from SDL's mouse coordinates onto the canvas, so
    clicks stay accurate whatever resolution the window/framebuffer was opened
    at and wherever the canvas sits inside it."""
    global _MOUSE_TO_CANVAS
    _MOUSE_TO_CANVAS = (scale[0], scale[1], offset[0], offset[1])


def _set_mouse_scale(
    canvas_size: tuple[int, int], display_size: tuple[int, int]
) -> None:
    """Convenience for the common case: the canvas covers the whole display."""
    _set_mouse_transform(
        (canvas_size[0] / display_size[0], canvas_size[1] / display_size[1])
    )


# -- geometry helpers -------------------------------------------------------


def centroid(vertices: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(vertices)
    return (sum(x for x, _ in vertices) / n, sum(y for _, y in vertices) / n)


def shrink_polygon(vertices, factor: float):
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
    """Filled polygon, antialiased where gfxdraw is available."""
    points = [(int(x), int(y)) for x, y in vertices]
    if _GFX is None:
        pygame.draw.polygon(surface, color, points)
    else:
        _GFX.filled_polygon(surface, points, color)
        _GFX.aapolygon(surface, points, color)


def outline_polygon(surface, points, color) -> None:
    if _GFX is None:
        pygame.draw.polygon(surface, color, points, 1)
    else:
        _GFX.aapolygon(surface, points, color)


def fill_circle(surface, cx, cy, radius, color) -> None:
    if _GFX is None:
        pygame.draw.circle(surface, color, (cx, cy), radius)
    else:
        _GFX.filled_circle(surface, cx, cy, radius, color)
        _GFX.aacircle(surface, cx, cy, radius, color)


def scale_color(color, factor: float):
    return tuple(min(255, int(c * factor)) for c in color)


def draw_tile(surface, vertices, base, *, raised: bool, shade: float = 1.0) -> None:
    """A classic minesweeper tile on an arbitrary convex polygon: raised
    tiles get light bevels on the edges facing the light (up-left) and
    dark bevels opposite; revealed tiles lie flat with a thin outline."""
    fill_polygon(surface, vertices, scale_color(base, shade))
    cx, cy = centroid(vertices)
    if raised:
        inset = shrink_polygon(vertices, 0.93)
        n = len(inset)
        for i in range(n):
            a, b = inset[i], inset[(i + 1) % n]
            mx, my = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy
            length = math.hypot(mx, my) or 1.0
            facing = (mx * TILE_LIGHT_DIR[0] + my * TILE_LIGHT_DIR[1]) / length
            bevel = BEVEL_LIGHT if facing > 0 else BEVEL_DARK
            pygame.draw.line(surface, scale_color(bevel, shade), a, b, 2 * S)
    else:
        points = [(int(x), int(y)) for x, y in vertices]
        outline_polygon(surface, points, scale_color(GRID_LINE, shade))


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


_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")


class FontCache:
    """Caches ``pygame.font.Font`` objects, keyed by pixel size.

    Text is drawn from TTFs vendored in ``assets/fonts`` so the game looks
    identical on desktop and in the browser (pygbag has no system fonts, so
    ``SysFont`` there silently fell back to pygame's generic default).
    ``get`` returns the UI face (Rubik, already bold); ``counter`` returns
    the segmented-LCD face (DSEG7) used for the mine/timer counters.
    ``FAMILY`` is only a last-resort fallback if a bundled file is missing.
    """

    FAMILY = "menlo, couriernew, monospace"
    _UI_FILE = os.path.join(_FONT_DIR, "Rubik-Bold.ttf")
    _COUNTER_FILE = os.path.join(_FONT_DIR, "DSEG7Classic-Bold.ttf")

    def __init__(self) -> None:
        pygame.font.init()
        self._ui: dict[int, pygame.font.Font] = {}
        self._counter: dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        """The UI/label/tile-number face."""
        if size not in self._ui:
            self._ui[size] = self._load(self._UI_FILE, size)
        return self._ui[size]

    def counter(self, size: int) -> pygame.font.Font:
        """The 7-segment LCD face for the mine/timer counters."""
        if size not in self._counter:
            self._counter[size] = self._load(self._COUNTER_FILE, size)
        return self._counter[size]

    def _load(self, path: str, size: int) -> pygame.font.Font:
        try:
            return pygame.font.Font(path, size)
        except (OSError, pygame.error):
            pass  # bundled file missing/unreadable; fall back to a system face
        try:
            font = pygame.font.SysFont(self.FAMILY, size, bold=True)
        except Exception:  # no system fonts in the browser (pygbag)
            font = pygame.font.Font(None, size)
            font.set_bold(True)
        return font


# -- glyphs ------------------------------------------------------------------


def draw_mine(surface, center, radius) -> None:
    cx, cy = int(center[0]), int(center[1])
    r = max(3, int(radius * 0.5))
    spike = radius * 0.85
    width = max(2, int(radius * 0.14))
    for dx, dy in ((1, 0), (0, 1), (0.7, 0.7), (0.7, -0.7)):
        start = (cx - dx * spike, cy - dy * spike)
        end = (cx + dx * spike, cy + dy * spike)
        pygame.draw.line(surface, MINE_COLOR, start, end, width)
    fill_circle(surface, cx, cy, r, MINE_COLOR)
    glint = max(1, r // 3)
    fill_circle(surface, cx - r // 3, cy - r // 3, glint, (255, 255, 255))


def draw_flag(surface, center, radius, *, wrong: bool) -> None:
    cx, cy = center
    top, bottom = cy - radius * 0.9, cy + radius * 0.9
    width = max(2, int(radius * 0.12))
    pygame.draw.line(surface, MINE_COLOR, (cx, top), (cx, bottom), width)
    fill_polygon(
        surface,
        [(cx, top), (cx - radius * 0.9, top + radius * 0.45), (cx, top + radius * 0.9)],
        FLAG_COLOR,
    )
    if wrong:  # misplaced flag revealed at game end
        r = radius * 0.95
        pygame.draw.line(surface, MINE_COLOR, (cx - r, cy - r), (cx + r, cy + r), width + 1)
        pygame.draw.line(surface, MINE_COLOR, (cx - r, cy + r), (cx + r, cy - r), width + 1)


def _draw_smiley_raw(surface, center, radius: int, state: GameState) -> None:
    """Smiley geometry at an arbitrary radius (drawn supersampled and
    cached by :func:`smiley_sprite`)."""
    cx, cy = int(center[0]), int(center[1])
    fill_circle(surface, cx, cy, radius, FACE_YELLOW)
    dark = (60, 46, 12)
    stroke = max(2, radius // 7)
    eye_dx, eye_y = int(radius * 0.38), cy - int(radius * 0.25)
    if state is GameState.LOST:
        for ex in (cx - eye_dx, cx + eye_dx):
            e = max(2, radius // 5)
            pygame.draw.line(surface, dark, (ex - e, eye_y - e), (ex + e, eye_y + e), stroke)
            pygame.draw.line(surface, dark, (ex - e, eye_y + e), (ex + e, eye_y - e), stroke)
        mouth = pygame.Rect(0, 0, radius, int(radius * 0.7))
        mouth.center = (cx, cy + int(radius * 0.62))
        pygame.draw.arc(surface, dark, mouth, math.radians(35), math.radians(145), stroke)
    else:
        if state is GameState.WON:  # sunglasses
            glass = max(3, radius // 3)
            for ex in (cx - eye_dx, cx + eye_dx):
                pygame.draw.rect(
                    surface, dark,
                    pygame.Rect(ex - glass // 2 - 1, eye_y - glass // 2, glass + 2, glass),
                    border_radius=max(2, glass // 3),
                )
            pygame.draw.line(
                surface, dark,
                (cx - eye_dx - glass, eye_y - 1), (cx + eye_dx + glass, eye_y - 1),
                stroke,
            )
        else:
            for ex in (cx - eye_dx, cx + eye_dx):
                fill_circle(surface, ex, eye_y, max(2, radius // 6), dark)
        mouth = pygame.Rect(0, 0, radius, int(radius * 0.8))
        mouth.center = (cx, cy + int(radius * 0.1))
        pygame.draw.arc(surface, dark, mouth, math.radians(215), math.radians(325), stroke)


_smiley_cache: dict[tuple[int, str], pygame.Surface] = {}


def smiley_sprite(radius: int, state: GameState) -> pygame.Surface:
    """The face button smiley, supersampled at 4x and cached."""
    key = (radius, state.value)
    if key not in _smiley_cache:
        big = radius * 4
        sprite = pygame.Surface((big * 2 + 4, big * 2 + 4), pygame.SRCALPHA)
        _draw_smiley_raw(sprite, (big + 2, big + 2), big, state)
        _smiley_cache[key] = pygame.transform.smoothscale(
            sprite, (radius * 2 + 1, radius * 2 + 1)
        )
    return _smiley_cache[key]


def _gloss(surface, rect: pygame.Rect, alpha: int = 55, radius: int = 0) -> None:
    """Blend a soft white highlight over the top part of ``rect``."""
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    top = pygame.Rect(rect.left, rect.top, rect.width, rect.height // 2)
    pygame.draw.rect(overlay, (255, 255, 255, alpha), top, border_radius=radius)
    surface.blit(overlay, (0, 0))


def make_icon(size: int = 512) -> pygame.Surface:
    """App icon: a mine in a hexagon on a macOS-style rounded square."""
    icon = pygame.Surface((size, size), pygame.SRCALPHA)
    margin = int(size * 0.05)
    plate = pygame.Rect(margin, margin, size - 2 * margin, size - 2 * margin)
    corner = int(size * 0.225)

    # base plate with a subtle vertical gradient
    steps = 48
    for i in range(steps):
        t = i / (steps - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip((238, 240, 244), (198, 202, 210)))
        band = pygame.Rect(
            plate.left,
            plate.top + plate.height * i // steps,
            plate.width,
            plate.height // steps + 2,
        )
        strip = pygame.Surface(icon.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(strip, (*color, 255), band)
        mask = pygame.Surface(icon.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), plate, border_radius=corner)
        strip.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        icon.blit(strip, (0, 0))
    pygame.draw.rect(icon, (150, 154, 162), plate, 2, border_radius=corner)

    # steel-blue hexagon
    cx = cy = size // 2
    r = size * 0.335
    hexagon = [
        (cx + r * math.cos(math.radians(60 * k - 90)),
         cy + r * math.sin(math.radians(60 * k - 90)))
        for k in range(6)
    ]
    fill_polygon(icon, hexagon, ICON_BLUE)
    inset = shrink_polygon(hexagon, 0.94)
    for i in range(6):
        a, b = inset[i], inset[(i + 1) % 6]
        mx, my = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy
        length = math.hypot(mx, my) or 1.0
        facing = (mx * TILE_LIGHT_DIR[0] + my * TILE_LIGHT_DIR[1]) / length
        bevel = ICON_BLUE_LIGHT if facing > 0 else ICON_BLUE_DARK
        pygame.draw.line(icon, bevel, a, b, max(3, size // 56))

    # the mine
    body = int(size * 0.13)
    spike = size * 0.21
    for dx, dy in ((1, 0), (0, 1), (0.7, 0.7), (0.7, -0.7)):
        start = (cx - dx * spike, cy - dy * spike)
        end = (cx + dx * spike, cy + dy * spike)
        pygame.draw.line(icon, MINE_COLOR, start, end, max(3, size // 36))
    fill_circle(icon, cx, cy, body, MINE_COLOR)
    glint = max(2, body // 3)
    fill_circle(icon, cx - body // 3, cy - body // 3, glint, (255, 255, 255))

    _gloss(icon, plate, alpha=36, radius=corner)
    return icon


def bevel_rect(
    surface, rect, fill, *, pressed: bool = False, border: int = 2 * S
) -> None:
    pygame.draw.rect(surface, fill, rect)
    top_left, bottom_right = (
        (BEVEL_DARK, BEVEL_LIGHT) if pressed else (BEVEL_LIGHT, BEVEL_DARK)
    )
    pygame.draw.line(surface, top_left, rect.topleft, rect.topright, border)
    pygame.draw.line(surface, top_left, rect.topleft, rect.bottomleft, border)
    pygame.draw.line(surface, bottom_right, rect.bottomleft, rect.bottomright, border)
    pygame.draw.line(surface, bottom_right, rect.topright, rect.bottomright, border)


# -- menu icons ---------------------------------------------------------------

ICON_SIZE = 44 * S
_icon_cache: dict[str, pygame.Surface] = {}


def _ngon_points(cx, cy, r, n, rotation=0):
    return [
        (cx + r * math.cos(math.radians(360 / n * k + rotation)),
         cy + r * math.sin(math.radians(360 / n * k + rotation)))
        for k in range(n)
    ]


def _hexagon_points(cx, cy, r, rotation=30):
    return _ngon_points(cx, cy, r, 6, rotation)


def _icon_shape(surface, points, fill=ICON_BLUE, outline=ICON_BLUE_DARK, width=5):
    fill_polygon(surface, points, fill)
    pts = [(int(x), int(y)) for x, y in points]
    pygame.draw.lines(surface, outline, True, pts, width)
    outline_polygon(surface, pts, outline)


def _icon_gloss(surface, bbox: pygame.Rect, alpha: int = 70) -> None:
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    highlight = pygame.Rect(
        bbox.left, bbox.top, bbox.width, int(bbox.height * 0.45)
    )
    pygame.draw.ellipse(overlay, (255, 255, 255, alpha), highlight)
    surface.blit(overlay, (0, 0))


def _icon_badge(s, cx, cy, r, shape: str) -> None:
    """A small light shape marking which tiling a surface uses."""
    if shape == "tri":
        points = [(cx, cy - r), (cx - r * 0.95, cy + r * 0.8), (cx + r * 0.95, cy + r * 0.8)]
    elif shape == "hex":
        points = _hexagon_points(cx, cy, r)
    else:  # square
        points = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
    _icon_shape(s, points, fill=ICON_BLUE_LIGHT, width=4)


# menu keys that reuse another key's drawing
_ICON_ALIASES = {
    "tri": "trigrid",
    "aperiodic": "penrose",
    "shaped": "triangle",
    "polyhedra": "cube",
}


def _render_icon(key: str) -> pygame.Surface:
    """Draw a menu icon supersampled at 4x, then smooth-scale down."""
    d = ICON_SIZE * 4
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d / 2

    key = _ICON_ALIASES.get(key, key)

    if key == "uniform":
        # one shape of each kind: the group of uniform tilings
        _icon_shape(s, [(d * 0.08, d * 0.08), (d * 0.48, d * 0.08),
                        (d * 0.48, d * 0.48), (d * 0.08, d * 0.48)])
        _icon_shape(s, _hexagon_points(d * 0.72, d * 0.28, d * 0.22))
        _icon_shape(s, [(d * 0.28, d * 0.9), (d * 0.08, d * 0.55),
                        (d * 0.48, d * 0.55)], fill=ICON_BLUE_LIGHT)
        _icon_shape(s, [(d * 0.52, d * 0.55), (d * 0.92, d * 0.55),
                        (d * 0.92, d * 0.9), (d * 0.52, d * 0.9)])
        _icon_gloss(s, pygame.Rect(d * 0.08, d * 0.08, d * 0.84, d * 0.84))
    elif key == "dual":
        # the Laves (dual) tilings: a pentagon and a rhombus, the shapes of
        # the two best-known duals (Cairo and rhombille)
        _icon_shape(s, _ngon_points(d * 0.34, d * 0.36, d * 0.28, 5, -90))
        _icon_shape(s, [(d * 0.72, d * 0.34), (d * 0.92, d * 0.62),
                        (d * 0.72, d * 0.9), (d * 0.52, d * 0.62)],
                    fill=ICON_BLUE_LIGHT)
        _icon_shape(s, [(d * 0.12, d * 0.66), (d * 0.44, d * 0.66),
                        (d * 0.3, d * 0.94), (d * -0.02, d * 0.94)],
                    fill=ICON_BLUE_LIGHT)
        _icon_gloss(s, pygame.Rect(d * 0.06, d * 0.08, d * 0.86, d * 0.84))
    elif key in ("flat", "square", "torus_tile"):
        gap, tile = d * 0.04, d * 0.42
        for ix in (0, 1):
            for iy in (0, 1):
                x = c - tile - gap / 2 + ix * (tile + gap)
                y = c - tile - gap / 2 + iy * (tile + gap)
                rect = [(x, y), (x + tile, y), (x + tile, y + tile), (x, y + tile)]
                _icon_shape(s, rect)
        _icon_gloss(s, pygame.Rect(d * 0.08, d * 0.08, d * 0.84, d * 0.84))
    elif key == "triangle":
        outer = [(c, d * 0.08), (d * 0.05, d * 0.9), (d * 0.95, d * 0.9)]
        _icon_shape(s, outer)
        inner = [(c - d * 0.22, d * 0.49), (c + d * 0.22, d * 0.49), (c, d * 0.9)]
        fill_polygon(s, inner, (0, 0, 0, 0))
        pygame.draw.lines(
            s, ICON_BLUE_DARK, True, [(int(x), int(y)) for x, y in inner], 5
        )
        _icon_gloss(s, pygame.Rect(d * 0.15, d * 0.1, d * 0.7, d * 0.7))
    elif key == "trigrid":
        w = d * 0.46
        for i in range(3):
            x = d * 0.04 + i * w * 0.5
            if i % 2 == 0:
                points = [(x, d * 0.85), (x + w, d * 0.85), (x + w / 2, d * 0.18)]
            else:
                points = [(x, d * 0.18), (x + w, d * 0.18), (x + w / 2, d * 0.85)]
            _icon_shape(s, points)
        _icon_gloss(s, pygame.Rect(d * 0.05, d * 0.12, d * 0.9, d * 0.75))
    elif key == "hex":
        _icon_shape(s, _hexagon_points(c, c, d * 0.44))
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.85))
    elif key == "hexhex":
        r = d * 0.155
        centers = [(c, c)] + [
            (c + 2 * r * 0.95 * math.cos(math.radians(60 * k)),
             c + 2 * r * 0.95 * math.sin(math.radians(60 * k)))
            for k in range(6)
        ]
        for hx, hy in centers:
            _icon_shape(s, _hexagon_points(hx, hy, r), width=4)
        _icon_gloss(s, pygame.Rect(d * 0.08, d * 0.08, d * 0.84, d * 0.84))
    elif key == "penrose":
        # a sun of five thick rhombi
        side, diag = d * 0.3, d * 0.3 * 1.618
        for k in range(5):
            angle = math.radians(72 * k - 90)
            points = [
                (c, c),
                (c + side * math.cos(angle - math.radians(36)),
                 c + side * math.sin(angle - math.radians(36))),
                (c + diag * math.cos(angle), c + diag * math.sin(angle)),
                (c + side * math.cos(angle + math.radians(36)),
                 c + side * math.sin(angle + math.radians(36))),
            ]
            _icon_shape(s, points, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.08, d * 0.06, d * 0.84, d * 0.6))
    elif key == "hat":
        # a single hat monotile silhouette (the aperiodic tridecagon)
        hr3 = math.sqrt(3) / 2
        ab = [(0, 0), (-1, -1), (0, -2), (2, -2), (2, -1), (4, -2), (5, -1),
              (4, 0), (3, 0), (2, 2), (0, 3), (0, 2), (-1, 2)]
        raw = [(a + 0.5 * b, hr3 * b) for a, b in ab]
        xs = [p[0] for p in raw]
        ys = [p[1] for p in raw]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        sc = d * 0.82 / span
        ox = (d - (max(xs) - min(xs)) * sc) / 2
        oy = (d - (max(ys) - min(ys)) * sc) / 2
        pts = [(ox + (x - min(xs)) * sc, oy + (max(ys) - y) * sc) for x, y in raw]
        _icon_shape(s, pts, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.06, d * 0.8, d * 0.55))
    elif key == "elongated":
        # a square row under a triangle row
        _icon_shape(s, [(d * 0.12, d * 0.5), (d * 0.5, d * 0.5),
                        (d * 0.5, d * 0.88), (d * 0.12, d * 0.88)], width=4)
        _icon_shape(s, [(d * 0.5, d * 0.5), (d * 0.88, d * 0.5),
                        (d * 0.88, d * 0.88), (d * 0.5, d * 0.88)], width=4)
        _icon_shape(s, [(d * 0.12, d * 0.5), (d * 0.5, d * 0.5), (d * 0.31, d * 0.12)],
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_shape(s, [(d * 0.5, d * 0.5), (d * 0.31, d * 0.12), (d * 0.69, d * 0.12)],
                    width=4)
        _icon_shape(s, [(d * 0.5, d * 0.5), (d * 0.88, d * 0.5), (d * 0.69, d * 0.12)],
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.1, d * 0.8, d * 0.7))
    elif key == "snubsquare":
        # an upright and a tilted square joined by triangles
        _icon_shape(s, _ngon_points(d * 0.32, d * 0.62, d * 0.26, 4, 45), width=4)
        _icon_shape(s, _ngon_points(d * 0.68, d * 0.36, d * 0.26, 4, 15), width=4)
        _icon_shape(s, [(d * 0.32, d * 0.25), (d * 0.5, d * 0.44), (d * 0.58, d * 0.14)],
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_shape(s, [(d * 0.5, d * 0.6), (d * 0.72, d * 0.82), (d * 0.86, d * 0.6)],
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.6))
    elif key == "kagome":
        _icon_shape(s, _hexagon_points(c, c, d * 0.3, 0), width=4)
        for k in range(3):
            angle = math.radians(120 * k - 90)
            tx = c + d * 0.42 * math.cos(angle)
            ty = c + d * 0.42 * math.sin(angle)
            _icon_shape(
                s, _ngon_points(tx, ty, d * 0.15, 3, 120 * k - 90),
                fill=ICON_BLUE_LIGHT, width=4,
            )
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.7))
    elif key == "snubhex":
        _icon_shape(s, _hexagon_points(c, c, d * 0.28), width=4)
        for k in range(6):
            angle = math.radians(60 * k)
            tx = c + d * 0.4 * math.cos(angle)
            ty = c + d * 0.4 * math.sin(angle)
            _icon_shape(
                s, _ngon_points(tx, ty, d * 0.12, 3, 60 * k + 30),
                fill=ICON_BLUE_LIGHT, width=3,
            )
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.7))
    elif key == "truncsquare":
        _icon_shape(s, _ngon_points(c, c, d * 0.42, 8, 22.5), width=4)
        _icon_shape(s, _ngon_points(d * 0.85, d * 0.85, d * 0.13, 4, 45),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.8))
    elif key == "trunchex":
        _icon_shape(s, _ngon_points(c, c, d * 0.42, 12, 15), width=4)
        _icon_shape(s, _ngon_points(d * 0.86, d * 0.82, d * 0.13, 3, -90),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.8))
    elif key == "rhombitrihex":
        # a hexagon with a square on top and a triangle in a corner
        _icon_shape(s, _hexagon_points(c, c + d * 0.06, d * 0.28, 0), width=4)
        _icon_shape(s, _ngon_points(c, d * 0.2, d * 0.13, 4, 45),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_shape(s, _ngon_points(d * 0.84, d * 0.8, d * 0.12, 3, 30),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.7))
    elif key == "trunctrihex":
        # a dodecagon flanked by a hexagon and a square badge
        _icon_shape(s, _ngon_points(c, c, d * 0.42, 12, 15), width=4)
        _icon_shape(s, _hexagon_points(d * 0.83, d * 0.83, d * 0.13, 0),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_shape(s, _ngon_points(d * 0.17, d * 0.83, d * 0.11, 4, 45),
                    fill=ICON_BLUE_LIGHT, width=3)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.8))
    elif key == "prismaticpent":
        # rows of pentagons: two stacked (the dual of elongated triangular)
        _icon_shape(s, _ngon_points(c, d * 0.32, d * 0.26, 5, -90), width=4)
        _icon_shape(s, _ngon_points(c, d * 0.68, d * 0.26, 5, 90),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.14, d * 0.08, d * 0.72, d * 0.7))
    elif key == "cairo":
        # two pentagons in the Cairo basketweave (dual of snub square)
        _icon_shape(s, _ngon_points(d * 0.37, d * 0.4, d * 0.28, 5, -108), width=4)
        _icon_shape(s, _ngon_points(d * 0.63, d * 0.6, d * 0.28, 5, 72),
                    fill=ICON_BLUE_LIGHT, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.08, d * 0.08, d * 0.84, d * 0.7))
    elif key == "rhombille":
        # three rhombi meeting as an isometric cube (dual of kagome)
        h = _hexagon_points(c, c, d * 0.42, -90)
        _icon_shape(s, [h[0], h[1], (c, c), h[5]], fill=ICON_BLUE_LIGHT, width=4)
        _icon_shape(s, [h[1], h[2], h[3], (c, c)], fill=ICON_BLUE, width=4)
        _icon_shape(s, [h[5], (c, c), h[3], h[4]], fill=ICON_BLUE_DARK, width=4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.4))
    elif key == "floret":
        # six pentagons pinwheeling round a centre (dual of snub hexagonal)
        for k in range(6):
            angle = math.radians(60 * k)
            px = c + d * 0.24 * math.cos(angle)
            py = c + d * 0.24 * math.sin(angle)
            _icon_shape(s, _ngon_points(px, py, d * 0.17, 5, 60 * k + 20),
                        fill=ICON_BLUE_LIGHT if k % 2 else ICON_BLUE, width=3)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.7))
    elif key == "tetrakis":
        # a square cut by both diagonals into four triangles
        sq = [(d * 0.12, d * 0.12), (d * 0.88, d * 0.12),
              (d * 0.88, d * 0.88), (d * 0.12, d * 0.88)]
        _icon_shape(s, sq, width=4)
        for a, b in (((c, c), sq[0]), ((c, c), sq[1]), ((c, c), sq[2]), ((c, c), sq[3])):
            pygame.draw.line(s, ICON_BLUE_DARK, a, b, 4)
        _icon_gloss(s, pygame.Rect(d * 0.12, d * 0.12, d * 0.76, d * 0.4))
    elif key == "triakis":
        # a triangle split from its centre into three (dual of trunc. hex.)
        outer = _ngon_points(c, c + d * 0.04, d * 0.46, 3, -90)
        _icon_shape(s, outer, width=4)
        for v in outer:
            pygame.draw.line(s, ICON_BLUE_DARK, (c, c + d * 0.04), v, 4)
        _icon_gloss(s, pygame.Rect(d * 0.18, d * 0.1, d * 0.64, d * 0.4))
    elif key == "deltoidal":
        # a ring of kites round a centre (dual of rhombitrihexagonal)
        h = _hexagon_points(c, c, d * 0.44, 0)
        mids = [( (h[k][0] + h[(k+1) % 6][0]) / 2, (h[k][1] + h[(k+1) % 6][1]) / 2 )
                for k in range(6)]
        for k in range(6):
            kite = [(c, c), mids[k - 1], h[k], mids[k]]
            _icon_shape(s, kite, fill=ICON_BLUE_LIGHT if k % 2 else ICON_BLUE, width=3)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.4))
    elif key == "kisrhombille":
        # a hexagon barycentrically cut into twelve right triangles
        h = _hexagon_points(c, c, d * 0.44, 0)
        mids = [( (h[k][0] + h[(k+1) % 6][0]) / 2, (h[k][1] + h[(k+1) % 6][1]) / 2 )
                for k in range(6)]
        _icon_shape(s, h, width=4)
        for pt in list(h) + mids:
            pygame.draw.line(s, ICON_BLUE_DARK, (c, c), pt, 3)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.08, d * 0.8, d * 0.4))
    elif key in ("sphere", "c80", "c180", "spheretri", "snubdodec"):
        fill_circle(s, int(c), int(c), int(d * 0.44), ICON_BLUE)
        pygame.draw.circle(s, ICON_BLUE_DARK, (int(c), int(c)), int(d * 0.44), 4)
        if key == "spheretri":
            _icon_badge(s, c, c, d * 0.2, "tri")
        elif key == "snubdodec":
            _icon_shape(s, _ngon_points(c, c - d * 0.06, d * 0.17, 5, -90),
                        fill=ICON_BLUE_LIGHT, width=4)
            for k in range(5):
                angle = math.radians(72 * k - 90)
                tx = c + d * 0.3 * math.cos(angle) * 1.05
                ty = c - d * 0.06 + d * 0.3 * math.sin(angle) * 1.05
                _icon_badge(s, tx, ty, d * 0.08, "tri")
        else:
            # pentagon center for the pentagonal solids, hexagon for C180
            sides = 6 if key == "c180" else 5
            inner = [
                (c + d * 0.2 * math.cos(math.radians(360 / sides * k - 90)),
                 c + d * 0.2 * math.sin(math.radians(360 / sides * k - 90)))
                for k in range(sides)
            ]
            _icon_shape(s, inner, fill=ICON_BLUE_LIGHT, width=4)
            if key in ("c80", "c180"):  # bond lines, fullerene style
                for k in range(sides):
                    angle = math.radians(360 / sides * k - 90)
                    x1 = c + d * 0.2 * math.cos(angle)
                    y1 = c + d * 0.2 * math.sin(angle)
                    x2 = c + d * 0.41 * math.cos(angle)
                    y2 = c + d * 0.41 * math.sin(angle)
                    pygame.draw.line(s, ICON_BLUE_DARK, (x1, y1), (x2, y2), 4)
        _icon_gloss(s, pygame.Rect(d * 0.13, d * 0.06, d * 0.62, d * 0.62), 90)
    elif key == "cube":
        # an isometric cube: three visible rhombic faces, grid-lined
        r = d * 0.4
        h = _hexagon_points(c, c, r, -90)  # h0 top, then clockwise
        faces = [
            ([h[0], h[1], (c, c), h[5]], ICON_BLUE_LIGHT),  # top
            ([h[1], h[2], h[3], (c, c)], ICON_BLUE),        # right
            ([h[5], (c, c), h[3], h[4]], ICON_BLUE_DARK),   # left
        ]

        def lerp(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        for quad, fill in faces:
            _icon_shape(s, quad, fill=fill, width=4)
            a, b, cc, dd = quad  # sides a-b and d-c, a-d and b-c
            for k in (1, 2):
                t = k / 3
                pygame.draw.line(s, ICON_BLUE_DARK, lerp(a, b, t), lerp(dd, cc, t), 3)
                pygame.draw.line(s, ICON_BLUE_DARK, lerp(a, dd, t), lerp(b, cc, t), 3)
        _icon_gloss(s, pygame.Rect(d * 0.12, d * 0.1, d * 0.76, d * 0.4))
    elif key == "cubeframe":
        # an isometric cube with a square hole punched through each of the
        # three visible faces: the bored-out Menger frame
        r = d * 0.4
        h = _hexagon_points(c, c, r, -90)  # h0 top, then clockwise
        faces = [
            ([h[0], h[1], (c, c), h[5]], ICON_BLUE_LIGHT),  # top
            ([h[1], h[2], h[3], (c, c)], ICON_BLUE),        # right
            ([h[5], (c, c), h[3], h[4]], ICON_BLUE_DARK),   # left
        ]
        for quad, fill in faces:
            _icon_shape(s, quad, fill=fill, width=4)
            fx = sum(p[0] for p in quad) / 4
            fy = sum(p[1] for p in quad) / 4
            hole = [(fx + (px - fx) * 0.44, fy + (py - fy) * 0.44) for px, py in quad]
            fill_polygon(s, hole, (0, 0, 0, 0))
            pygame.draw.lines(
                s, ICON_BLUE_DARK, True, [(int(x), int(y)) for x, y in hole], 3
            )
        _icon_gloss(s, pygame.Rect(d * 0.12, d * 0.1, d * 0.76, d * 0.4))
    elif key == "steppedbipyramid":
        # a terraced diamond: square slabs widest at the equator, tapering
        # up and down (a stepped bipyramid seen head-on)
        widths = (0.34, 0.58, 0.82, 0.58, 0.34)
        shades = (ICON_BLUE_LIGHT, ICON_BLUE_LIGHT, ICON_BLUE,
                  ICON_BLUE_DARK, ICON_BLUE_DARK)
        slab = d * 0.135
        top = c - slab * len(widths) / 2
        for idx, w in enumerate(widths):
            ww = d * w
            y = top + idx * slab
            rect = [(c - ww / 2, y), (c + ww / 2, y),
                    (c + ww / 2, y + slab), (c - ww / 2, y + slab)]
            _icon_shape(s, rect, fill=shades[idx], width=4)
        _icon_gloss(s, pygame.Rect(d * 0.12, d * 0.14, d * 0.76, d * 0.34))
    elif key == "tetrahedron":
        # a tetrahedron seen down a vertex: outer triangle with edges to
        # the center, each sub-face lightly triangulated
        outer = _ngon_points(c, c + d * 0.04, d * 0.46, 3, -90)
        shades = (ICON_BLUE_LIGHT, ICON_BLUE, ICON_BLUE_DARK)

        def lerp(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        for k in range(3):
            a, b = outer[k], outer[(k + 1) % 3]
            _icon_shape(s, [a, b, (c, c)], fill=shades[k], width=4)
            mid = lerp(a, b, 0.5)
            pygame.draw.line(s, ICON_BLUE_DARK, mid, (c, c), 3)
            pygame.draw.line(s, ICON_BLUE_DARK, lerp(a, (c, c), 0.5), lerp(b, (c, c), 0.5), 3)
        _icon_gloss(s, pygame.Rect(d * 0.18, d * 0.1, d * 0.64, d * 0.4))
    elif key == "tetraframe":
        # a level-1 Sierpiński tetrahedron seen down a vertex: the three
        # corner sub-triangles kept, the middle triangle removed
        outer = _ngon_points(c, c + d * 0.04, d * 0.46, 3, -90)
        shades = (ICON_BLUE_LIGHT, ICON_BLUE, ICON_BLUE_DARK)

        def lerp(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        mids = [lerp(outer[k], outer[(k + 1) % 3], 0.5) for k in range(3)]
        for k in range(3):
            _icon_shape(s, [outer[k], mids[k], mids[(k - 1) % 3]],
                        fill=shades[k], width=4)
        _icon_gloss(s, pygame.Rect(d * 0.18, d * 0.1, d * 0.64, d * 0.4))
    elif key == "torus":
        band = pygame.Rect(d * 0.04, d * 0.22, d * 0.92, d * 0.56)
        pygame.draw.ellipse(s, ICON_BLUE, band)
        pygame.draw.ellipse(s, ICON_BLUE_DARK, band, 4)
        hole = pygame.Rect(0, 0, d * 0.34, d * 0.18)
        hole.center = (int(c), int(c))
        pygame.draw.ellipse(s, (0, 0, 0, 0), hole)
        pygame.draw.ellipse(s, ICON_BLUE_DARK, hole, 4)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.24, d * 0.8, d * 0.34), 80)
    elif key == "mobius":
        band = pygame.Rect(d * 0.05, d * 0.16, d * 0.9, d * 0.68)
        pygame.draw.ellipse(s, ICON_BLUE, band)
        pygame.draw.ellipse(s, ICON_BLUE_DARK, band, 4)
        hole = pygame.Rect(0, 0, d * 0.42, d * 0.26)
        hole.center = (int(c), int(c))
        pygame.draw.ellipse(s, (0, 0, 0, 0), hole)
        pygame.draw.ellipse(s, ICON_BLUE_DARK, hole, 4)
        # the twist at the front
        pygame.draw.line(s, ICON_BLUE_DARK, (c - d * 0.09, d * 0.84), (c + d * 0.09, d * 0.63), 6)
        pygame.draw.line(s, ICON_BLUE_LIGHT, (c - d * 0.09, d * 0.63), (c + d * 0.09, d * 0.84), 6)
        _icon_gloss(s, pygame.Rect(d * 0.1, d * 0.18, d * 0.8, d * 0.3), 80)
    elif key == "cylinder":
        top = pygame.Rect(d * 0.18, d * 0.08, d * 0.64, d * 0.24)
        body = [
            (d * 0.18, d * 0.2), (d * 0.82, d * 0.2),
            (d * 0.82, d * 0.8), (d * 0.18, d * 0.8),
        ]
        fill_polygon(s, body, ICON_BLUE)
        bottom = pygame.Rect(d * 0.18, d * 0.68, d * 0.64, d * 0.24)
        pygame.draw.ellipse(s, ICON_BLUE, bottom)
        pygame.draw.arc(s, ICON_BLUE_DARK, bottom, math.radians(180), math.radians(360), 4)
        pygame.draw.line(s, ICON_BLUE_DARK, (d * 0.18, d * 0.2), (d * 0.18, d * 0.8), 4)
        pygame.draw.line(s, ICON_BLUE_DARK, (d * 0.82, d * 0.2), (d * 0.82, d * 0.8), 4)
        pygame.draw.ellipse(s, ICON_BLUE_LIGHT, top)
        pygame.draw.ellipse(s, ICON_BLUE_DARK, top, 4)
        _icon_gloss(s, pygame.Rect(d * 0.2, d * 0.26, d * 0.6, d * 0.5), 60)
    else:
        fill_circle(s, int(c), int(c), int(d * 0.4), ICON_BLUE)
        pygame.draw.circle(s, ICON_BLUE_DARK, (int(c), int(c)), int(d * 0.4), 2)

    return s  # supersampled; menu_icon scales it down


def menu_icon(key: str, size: int = ICON_SIZE) -> pygame.Surface:
    cache_key = (key, size)
    if cache_key not in _icon_cache:
        _icon_cache[cache_key] = pygame.transform.smoothscale(
            _render_icon(key), (size, size)
        )
    return _icon_cache[cache_key]


# -- game screens ------------------------------------------------------------


class BaseGameScreen:
    """Shared game lifecycle, header and input handling; subclasses supply
    geometry (cell polygons, hit testing and board drawing)."""

    def __init__(self, mode: str, difficulty: str = "easy") -> None:
        self.mode = mode
        self.difficulty = difficulty
        # extra height handed down by the web presenter to fill the window; the
        # header stays at the top and the board is centred in the space below
        self._view_h: int | None = None
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
    def natural_size(self) -> tuple[int, int]:
        """The board's own tight size, ignoring any web viewport padding."""
        raise NotImplementedError

    @property
    def size(self) -> tuple[int, int]:
        nat = self.natural_size
        if self._view_h is not None and self._view_h > nat[1]:
            return (nat[0], self._view_h)
        return nat

    @property
    def board_shift(self) -> int:
        """Downward shift that centres the board in the space below the header
        when the web presenter has given the screen extra height."""
        return max(0, (self.size[1] - self.natural_size[1]) // 2)

    def set_viewport_height(self, height: int) -> None:
        """Fill this much canvas height (web build); the desktop leaves it at
        the natural height, so its layout is unchanged."""
        if height == self._view_h:
            return
        self._view_h = height
        self._relayout()

    def _relayout(self) -> None:
        """Re-place geometry after the viewport height changed."""

    # Boards share one fixed web scale (see WEB_REF_WIDTH) so switching boards
    # never resizes the UI; a board wider than this is shrunk to fit.
    web_ref_width = WEB_REF_WIDTH

    @property
    def elapsed(self) -> int:
        if self.started_at is None:
            return 0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return min(999, int(end - self.started_at))

    @property
    def face_rect(self) -> pygame.Rect:
        return pygame.Rect(self.size[0] // 2 - 20 * S, MARGIN + 2 * S, 40 * S, 40 * S)

    @property
    def menu_rect(self) -> pygame.Rect:
        """The back-to-menu button in the header."""
        return pygame.Rect(MARGIN, MARGIN + 4 * S, 40 * S, 36 * S)

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
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.menu_rect.collidepoint(event.pos)
            ):
                return "menu"
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
            draw_tile(surface, vertices, face, raised=False, shade=shade)
        else:
            draw_tile(surface, vertices, HIDDEN_FACE, raised=True, shade=shade)

        if show_mine:
            draw_mine(surface, center, glyph_radius)
        elif state is CellState.FLAGGED:
            wrong = lost and not game.is_mine(cell)
            draw_flag(surface, center, glyph_radius, wrong=wrong)
        elif state is CellState.REVEALED:
            n = game.adjacent_mines(cell)
            if n:
                color = NUMBER_COLORS.get(n, TEXT)
                size = max(10 * S, int(glyph_radius * 1.5))
                text = fonts.get(size).render(str(n), True, color)
                surface.blit(text, text.get_rect(center=center))

    def draw_header(self, surface, fonts: FontCache) -> None:
        width = self.size[0]
        mouse = canvas_mouse()

        rect = self.menu_rect
        bevel_rect(surface, rect, BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON)
        arrow = [
            (rect.centerx + 5 * S, rect.centery - 8 * S),
            (rect.centerx - 5 * S, rect.centery),
            (rect.centerx + 5 * S, rect.centery + 8 * S),
        ]
        pygame.draw.lines(surface, TEXT, False, arrow, 3 * S)

        counter = f"{max(-99, min(999, self.game.flags_remaining)):03d}"
        self.draw_counter(surface, fonts, counter, x=rect.right + 8 * S)

        timer = f"{self.elapsed:03d}"
        timer_width = fonts.counter(24 * S).size(timer)[0] + 20 * S
        self.draw_counter(surface, fonts, timer, x=width - MARGIN - timer_width)

        face = self.face_rect
        bevel_rect(surface, face, BUTTON_HOVER if face.collidepoint(mouse) else BUTTON)
        sprite = smiley_sprite(14 * S, self.game.state)
        surface.blit(sprite, sprite.get_rect(center=face.center))

    def draw_counter(self, surface, fonts: FontCache, value: str, *, x: int) -> None:
        text = fonts.counter(24 * S).render(value, True, COUNTER_FG)
        box = pygame.Rect(x, MARGIN + 4 * S, text.get_width() + 20 * S, 36 * S)
        pygame.draw.rect(surface, PANEL, box, border_radius=6 * S)
        surface.blit(text, text.get_rect(center=box.center))


class GameScreen(BaseGameScreen):
    """Flat boards: static polygons straight from the board definition."""

    def _setup_geometry(self) -> None:
        offset_x, offset_y = MARGIN, MARGIN + HEADER + self.board_shift
        self.polygons = {
            cell: [(x * S + offset_x, y * S + offset_y) for x, y in vertices]
            for cell, vertices in self.board.polygons.items()
        }
        self.centers = {
            cell: centroid(vertices) for cell, vertices in self.polygons.items()
        }
        # per cell: tilings like Penrose mix cells of different sizes
        self.glyph_radius = {
            cell: inradius(vertices) * 0.85
            for cell, vertices in self.polygons.items()
        }

    # re-place the polygons when the web viewport height changes
    _relayout = _setup_geometry

    @property
    def natural_size(self) -> tuple[int, int]:
        return (
            math.ceil(self.board.width * S) + 2 * MARGIN,
            math.ceil(self.board.height * S) + HEADER + 2 * MARGIN,
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
                self.centers[cell], self.glyph_radius[cell],
            )


class GameScreen3D(BaseGameScreen):
    """Curved boards rendered with an orthographic projection: faces are
    lit by a fixed light, depth-sorted and painted far to near. Closed
    surfaces cull back faces; open or one-sided surfaces (cylinder,
    Möbius strip) draw both sides. Dragging rotates; a short click
    reveals."""

    VIEWPORT = 540 * S
    ROTATE_SPEED = 0.008 / S  # radians per canvas pixel of drag

    def _initial_rotation(self):
        # flat-faced solids show only one face head-on; a 3/4 turn reveals
        # three faces at once
        if self.mode in ("cube", "tetrahedron", "cubeframe", "steppedbipyramid"):
            return mat_mul(rot_x(-0.5), rot_y(0.6))
        # a tetrahedron viewed down a 2-fold axis looks like a flat square;
        # turn to a vertex-first 3/4 view so the frame's gaps read clearly
        if self.mode == "tetraframe":
            return mat_mul(rot_x(-0.62), rot_y(0.45))
        # wrapped surfaces tilt by their SurfaceSpec hint (donut, cylinder,
        # Möbius strip); everything else faces straight on
        tilt = view_hint(self.mode)
        return rot_x(tilt) if tilt is not None else IDENTITY

    def _setup_geometry(self) -> None:
        self.rotation = self._initial_rotation()
        self.scale = (self.VIEWPORT / 2 - 24 * S) / self.board.radius
        self._drag_from = None
        self._dragged = False
        self._frame = None  # projected geometry, rebuilt after rotation

    @property
    def natural_size(self) -> tuple[int, int]:
        return (
            self.VIEWPORT + 2 * MARGIN,
            self.VIEWPORT + HEADER + 2 * MARGIN,
        )

    def _relayout(self) -> None:
        self._frame = None  # cy depends on board_shift; reproject

    def _project(self):
        """Rotate, cull, light and depth-sort the cells. Returns a
        far-to-near list of (depth, cell, polygon, center, radius, shade)."""
        if self._frame is not None:
            return self._frame
        cx = self.size[0] / 2
        cy = MARGIN + HEADER + self.VIEWPORT / 2 + self.board_shift
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
                shade = 0.72 + 0.28 * abs(light)
                if n[2] < 0:
                    shade *= 0.82  # inside/back of the surface: dimmer
            else:
                shade = 0.78 + 0.22 * max(0.0, light)
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
        step = 40 * S  # canvas-pixels-worth of rotation per key press
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
            # vertical drag is inverted: dragging up tilts the top toward you
            self.rotate(event.rel[0], -event.rel[1])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag_from is not None and not self._dragged:
                cell = self.cell_at(event.pos)
                if cell is not None:
                    self.click(cell)
            self._drag_from = None
            self._dragged = False

    def draw_board(self, surface, fonts: FontCache) -> None:
        for _, cell, polygon, center, glyph_radius, shade in self._project():
            self.draw_cell(surface, fonts, cell, polygon, center, glyph_radius, shade)


def make_screen(mode: str, difficulty: str) -> BaseGameScreen:
    cls = GameScreen3D if mode in MODES_3D else GameScreen
    return cls(mode, difficulty)


# -- menu screen ---------------------------------------------------------------


class MenuScreen:
    """Up to three pages: pick a group, then a tiling, then — for the
    periodic tilings — a surface. A surface a tiling cannot wrap (snub
    hexagonal on the Möbius strip) is shown disabled."""

    WIDTH = 460 * S
    ITEM_HEIGHT = 58 * S
    ITEM_STEP = 70 * S

    def __init__(self, difficulty: str = "easy") -> None:
        self.difficulty = difficulty
        self.group: str | None = None  # None = group page
        self.tiling: str | None = None  # periodic group: tiling page done
        # extra height handed down by the web presenter to fill the window; the
        # title stays at the top, the difficulty row drops to the bottom and the
        # mode list is centred in the space between
        self._view_h: int | None = None

    def set_viewport_height(self, height: int) -> None:
        self._view_h = height

    def _via_tilings(self) -> bool:
        """Whether the current group navigates tiling -> surface. Signalled
        by an empty mode list in GROUPS (the uniform and dual-uniform groups
        route through GROUP_TILINGS); the others list their modes directly."""
        return self.group is not None and not GROUPS[self.group][1]

    def _items(self) -> list[tuple[str, str, bool]]:
        """(key, label, enabled) rows for the current page."""
        if self.group is None:
            return [(key, label, True) for key, (label, _) in GROUPS.items()]
        if self._via_tilings():
            if self.tiling is None:
                return [(key, TILINGS[key][0], True)
                        for key in GROUP_TILINGS[self.group]]
            surfaces = TILINGS[self.tiling][1]
            return [
                (key, label, key in surfaces)
                for key, label in SURFACE_LABELS.items()
            ]
        return [
            (mode, MODE_LABELS[mode], True) for mode in GROUPS[self.group][1]
        ]

    def _subtitle(self) -> str:
        if self.group is None:
            return "choose a board"
        if self._via_tilings():
            if self.tiling is None:
                return GROUPS[self.group][0] + " — choose a tiling"
            return TILINGS[self.tiling][0] + " — choose a surface"
        return GROUPS[self.group][0] + " — choose a tiling"

    def _back(self) -> None:
        if self.tiling is not None:
            self.tiling = None
        else:
            self.group = None

    def layout(self):
        items = self._items()
        # the tiling pages (11 tilings) go in two columns; every other page
        # is a single column. Two-column rows are narrower, so they use the
        # tighter compact sizing too.
        two_col = self._via_tilings() and self.tiling is None
        compact = two_col or len(items) > 8
        item_height = 42 * S if compact else self.ITEM_HEIGHT
        item_step = 50 * S if compact else self.ITEM_STEP
        rects = []
        top = 96 * S
        if two_col:
            margin, gap = 26 * S, 14 * S
            col_w = (self.WIDTH - 2 * margin - gap) / 2
            rows = (len(items) + 1) // 2  # first column gets the extra row
            for i, (key, label, enabled) in enumerate(items):
                col, row = divmod(i, rows)
                x = margin + col * (col_w + gap)
                rects.append(
                    (pygame.Rect(x, top + row * item_step, col_w, item_height),
                     key, label, enabled)
                )
            y = top + rows * item_step
        else:
            y = top
            for key, label, enabled in items:
                rects.append(
                    (
                        pygame.Rect(50 * S, y, self.WIDTH - 100 * S, item_height),
                        key,
                        label,
                        enabled,
                    )
                )
                y += item_step
        items_height = y - top
        natural_height = y + 14 * S + 40 * S + 30 * S
        # on the web the presenter hands down extra height to fill the window:
        # pin the difficulty row to the bottom and centre the modes between it
        # and the title
        total = (
            self._view_h
            if self._view_h is not None and self._view_h > natural_height
            else natural_height
        )
        diff_y = total - 30 * S - 40 * S
        shift = max(0, ((diff_y - 14 * S - top) - items_height) // 2)
        if shift:
            for rect, *_ in rects:
                rect.move_ip(0, shift)
        difficulty_buttons = []
        button_width = 110 * S
        x = (self.WIDTH - 3 * button_width - 2 * 12 * S) // 2
        for difficulty_key in DIFFICULTIES:
            difficulty_buttons.append(
                (pygame.Rect(x, diff_y, button_width, 40 * S), difficulty_key)
            )
            x += button_width + 12 * S
        back = (
            pygame.Rect(16 * S, 26 * S, 84 * S, 34 * S)
            if self.group is not None
            else None
        )
        return {
            "items": rects,
            "difficulty": difficulty_buttons,
            "back": back,
            "compact": compact,
            "height": total,
        }

    @property
    def natural_size(self) -> tuple[int, int]:
        view, self._view_h = self._view_h, None
        try:
            return (self.WIDTH, self.layout()["height"])
        finally:
            self._view_h = view

    @property
    def size(self) -> tuple[int, int]:
        return (self.WIDTH, self.layout()["height"])

    # the menu fills the browser window edge to edge (scaled to its own width)
    web_ref_width = WIDTH

    def handle_event(self, event: pygame.event.Event):
        """Returns "quit", ("start", mode), or None."""
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.group is not None:
                    self._back()
                    return None
                return "quit"
            if event.key in DIFFICULTY_KEYS:
                self.difficulty = DIFFICULTY_KEYS[event.key]
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            layout = self.layout()
            if layout["back"] is not None and layout["back"].collidepoint(event.pos):
                self._back()
                return None
            for rect, difficulty_key in layout["difficulty"]:
                if rect.collidepoint(event.pos):
                    self.difficulty = difficulty_key
                    return None
            for rect, key, _, enabled in layout["items"]:
                if not rect.collidepoint(event.pos):
                    continue
                if not enabled:
                    return None
                if self.group is None:
                    self.group = key
                elif self._via_tilings() and self.tiling is None:
                    self.tiling = key
                elif self._via_tilings():
                    return ("start", TILINGS[self.tiling][1][key])
                else:
                    return ("start", key)
                return None
        return None

    def draw(self, surface: pygame.Surface, fonts: FontCache) -> None:
        surface.fill(BG)
        mouse = canvas_mouse()
        layout = self.layout()

        title = fonts.get(30 * S).render("MINESWEEPER", True, TEXT)
        surface.blit(title, title.get_rect(center=(self.WIDTH // 2, 44 * S)))
        subtitle = fonts.get(14 * S).render(self._subtitle(), True, MUTED)
        surface.blit(subtitle, subtitle.get_rect(center=(self.WIDTH // 2, 72 * S)))

        if layout["back"] is not None:
            rect = layout["back"]
            bevel_rect(
                surface, rect, BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON
            )
            label = fonts.get(14 * S).render("< back", True, TEXT)
            surface.blit(label, label.get_rect(center=rect.center))

        compact = layout["compact"]
        icon_size = (34 if compact else 44) * S
        label_size = (15 if compact else 18) * S
        for rect, key, label_text, enabled in layout["items"]:
            hover = enabled and rect.collidepoint(mouse)
            bevel_rect(surface, rect, BUTTON_HOVER if hover else BUTTON)
            icon = menu_icon(key, icon_size).copy()
            if not enabled:
                icon.set_alpha(70)
            surface.blit(icon, icon.get_rect(midleft=(rect.left + 10 * S, rect.centery)))
            text_x = rect.left + 10 * S + icon_size + 12 * S
            avail = rect.right - text_x - 10 * S  # shrink long labels to fit
            size = label_size
            label = fonts.get(size).render(label_text, True, TEXT if enabled else MUTED)
            while label.get_width() > avail and size > 11 * S:
                size -= 1 * S
                label = fonts.get(size).render(
                    label_text, True, TEXT if enabled else MUTED
                )
            surface.blit(label, label.get_rect(midleft=(text_x, rect.centery)))
            if not enabled:  # say why, quietly
                note = fonts.get(11 * S).render("impossible", True, MUTED)
                surface.blit(
                    note, note.get_rect(midright=(rect.right - 12 * S, rect.centery))
                )

        for rect, difficulty_key in layout["difficulty"]:
            selected = difficulty_key == self.difficulty
            fill = SELECTED if selected else (
                BUTTON_HOVER if rect.collidepoint(mouse) else BUTTON
            )
            bevel_rect(surface, rect, fill, pressed=selected)
            label = fonts.get(15 * S).render(difficulty_key.capitalize(), True, TEXT)
            surface.blit(label, label.get_rect(center=rect.center))


# -- application -------------------------------------------------------------


def _scale_mouse_event(event: pygame.event.Event) -> pygame.event.Event:
    """Translate a window-space mouse event into canvas coordinates."""
    sx, sy, ox, oy = _MOUSE_TO_CANVAS
    if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        return pygame.event.Event(
            event.type,
            pos=(round(event.pos[0] * sx + ox), round(event.pos[1] * sy + oy)),
            button=event.button,
        )
    if event.type == pygame.MOUSEMOTION:
        return pygame.event.Event(
            event.type,
            pos=(round(event.pos[0] * sx + ox), round(event.pos[1] * sy + oy)),
            rel=(round(event.rel[0] * sx), round(event.rel[1] * sy)),
            buttons=event.buttons,
        )
    return event


class _DesktopPresenter:
    """Presents the supersampled canvas in a high-DPI (Retina) window.

    The window is created at the logical point size (``canvas / S``) with
    ``allow_high_dpi`` so macOS gives it a backing store at the display's
    native pixel density -- twice the points on a Retina panel. We render
    through an ``_sdl2`` renderer/texture whose output is that full physical
    buffer, so the frame lands 1:1 on the device pixels instead of being a
    low-resolution surface the OS then upscales. On a 2x display the physical
    buffer equals the canvas size exactly, so the frame is presented with no
    resampling at all; on a 1x display it is smooth-downscaled (the same
    supersampling antialiasing as before)."""

    def __init__(self, icon: pygame.Surface) -> None:
        from pygame._sdl2 import video  # desktop only; absent in the wasm build

        self._video = video
        self._icon = icon
        self._window: object | None = None
        self._renderer: object | None = None
        self._points: tuple[int, int] | None = None
        self._drawable: tuple[int, int] = (0, 0)

    def ensure(self, canvas_size: tuple[int, int]) -> None:
        points = (canvas_size[0] // S, canvas_size[1] // S)
        if points == self._points:
            return
        self._points = points
        if self._window is None:
            self._window = self._video.Window(
                "Minesweeper", size=points, allow_high_dpi=True
            )
            self._window.set_icon(self._icon)
            self._renderer = self._video.Renderer(self._window)
        else:
            self._window.size = points
        # the renderer output is the physical (Retina) pixel size of the window
        self._drawable = tuple(self._renderer.get_viewport().size)
        # SDL reports mouse events in the window's logical points, not pixels
        _set_mouse_scale(canvas_size, points)

    def viewport_height(self, ref_width: int, natural: tuple[int, int]) -> int:
        return natural[1]  # desktop keeps each screen's natural height

    def present(self, canvas: pygame.Surface, ref_width: int | None = None) -> None:
        self.ensure(canvas.get_size())
        frame = (
            canvas
            if self._drawable == canvas.get_size()
            else pygame.transform.smoothscale(canvas, self._drawable)
        )
        texture = self._video.Texture.from_surface(self._renderer, frame)
        self._renderer.clear()
        texture.draw()
        self._renderer.present()

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()


class _WebPresenter:
    """Presents the canvas in the browser, filling the whole window.

    pygbag's template sizes the canvas element once at boot and never revisits
    it. Previously we matched the framebuffer to the board's own aspect ratio,
    which left the canvas smaller than the window -- gaps (letterbox bars) above
    and below on a tall phone -- and, because the fit scale depended on each
    board's size, the whole UI changed scale from one screen to the next.

    Instead the framebuffer is the full visible viewport (``visualViewport`` so
    the mobile address bar is excluded, times ``devicePixelRatio`` so a
    Retina/HiDPI phone gets its extra sharpness), the CSS box is the full
    window, and the background fills it edge to edge -- no gaps, ever. The
    screen is drawn onto its own canvas, scaled by a factor derived from its
    ``web_ref_width`` and the window width (constant across boards), and pinned
    to the top so the counters/smiley sit just under the address bar; oversized
    screens are clamped down to stay fully on screen."""

    def __init__(self) -> None:
        import platform  # pygbag's platform module exposes the DOM

        self._dom = platform.window
        self._display: pygame.Surface | None = None
        self._phys: tuple[int, int] = (0, 0)

    def _viewport(self) -> tuple[float, float, float]:
        """The visible viewport (CSS px) and device-pixel ratio. ``visualViewport``
        excludes the mobile browser's address bar; ``innerWidth``/``innerHeight``
        are the fallback where it is missing."""
        dom = self._dom
        vv = getattr(dom, "visualViewport", None)
        w = (getattr(vv, "width", 0) if vv is not None else 0) or dom.innerWidth
        h = (getattr(vv, "height", 0) if vv is not None else 0) or dom.innerHeight
        dpr = getattr(dom, "devicePixelRatio", 1) or 1
        return w, h, dpr

    def _resize(self) -> tuple[int, int]:
        """Match the framebuffer and CSS box to the current viewport; returns the
        physical (device-pixel) size."""
        w, h, dpr = self._viewport()
        phys = (max(1, round(w * dpr)), max(1, round(h * dpr)))
        if phys != self._phys:
            self._phys = phys
            self._display = pygame.display.set_mode(phys)
            style = self._dom.canvas.style
            style.width = f"{w}px"
            style.height = f"{h}px"
        return phys

    def ensure(self, canvas_size: tuple[int, int]) -> None:
        self._resize()

    def viewport_height(self, ref_width: int, natural: tuple[int, int]) -> int:
        """Canvas height the screen should fill so it reaches the bottom of the
        window at the shared scale (see ``present``)."""
        phys = self._resize()
        nat_w, nat_h = natural
        ref = ref_width or WEB_REF_WIDTH
        scale = min(phys[0] / ref, phys[0] / nat_w, phys[1] / nat_h)
        return max(nat_h, round(phys[1] / scale))

    def present(self, canvas: pygame.Surface, ref_width: int | None = None) -> None:
        phys = self._resize()
        assert self._display is not None
        nat = canvas.get_size()
        ref = ref_width or WEB_REF_WIDTH
        # device pixels per canvas pixel: fixed by the window width and the
        # design reference so it does not jump between boards, then clamped so
        # a screen wider or taller than the window still fits whole
        scale = min(phys[0] / ref, phys[0] / nat[0], phys[1] / nat[1])
        # clamp against float rounding so the centred blit always fits the frame
        size = (
            min(phys[0], max(1, round(nat[0] * scale))),
            min(phys[1], max(1, round(nat[1] * scale))),
        )
        # centre horizontally, pin to the top so the header sits under the
        # address bar and the spare room falls below the board
        offset = ((phys[0] - size[0]) // 2, 0)
        self._display.fill(BG)
        pygame.transform.smoothscale(canvas, size, self._display.subsurface(
            pygame.Rect(offset, size)
        ))
        pygame.display.flip()
        # map framebuffer clicks back through the centring offset and scale
        _set_mouse_transform(
            (1.0 / scale, 1.0 / scale),
            (-offset[0] / scale, -offset[1] / scale),
        )

    def close(self) -> None:
        pass


class App:
    def __init__(self, mode: str | None = None, difficulty: str = "easy") -> None:
        self.menu = MenuScreen(difficulty)
        self.screen = (
            make_screen(mode, difficulty) if mode is not None else self.menu
        )

    async def run_async(self) -> None:
        """Main loop. Async so the browser build (pygbag) can yield to the
        event loop every frame; on the desktop it runs under asyncio.run."""
        pygame.init()
        pygame.display.set_caption("Minesweeper")
        if sys.platform == "emscripten":
            presenter: _WebPresenter | _DesktopPresenter = _WebPresenter()
        else:
            presenter = _DesktopPresenter(make_icon())
        # open the display before allocating the canvas so the canvas inherits
        # the display's pixel format -- otherwise the browser build's first
        # frames come out with red/blue swapped until the next set_mode
        presenter.ensure(self.screen.size)
        canvas = pygame.Surface(self.screen.size)
        fonts = FontCache()
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                result = self.screen.handle_event(_scale_mouse_event(event))
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
            # let the presenter grow the screen to fill the window height; the
            # screen distributes the extra room (desktop leaves it at natural)
            self.screen.set_viewport_height(
                presenter.viewport_height(
                    self.screen.web_ref_width, self.screen.natural_size
                )
            )
            if canvas.get_size() != self.screen.size:
                canvas = pygame.Surface(self.screen.size)
            self.screen.draw(canvas, fonts)
            presenter.present(canvas, self.screen.web_ref_width)
            await asyncio.sleep(0)  # hand control back to the browser
            clock.tick(30)
        presenter.close()
        pygame.quit()

    def run(self) -> None:
        asyncio.run(self.run_async())


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
