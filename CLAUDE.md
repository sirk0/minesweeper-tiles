# Minesweeper (pygame)

A minesweeper clone with flat and 3D boards (sphere, fullerenes, cube,
tetrahedron, donut, Möbius strip, cylinder). Python 3.13 (see
`.python-version`), only dependency: `pygame-ce`.

## Architecture

- `minesweeper/game.py` — game rules over an arbitrary cell graph
  (`Game(adjacency, mine_count)`); knows nothing about geometry or UI.
- `minesweeper/boards/` — board builders, a package. Cells are polygons
  whose vertices have exact hashable ids (integer lattice points in 2D,
  symbolic/barycentric keys in 3D); two cells are neighbors when they
  share a vertex. Modules: `core` (`Board`/`Board3D`, adjacency, topology
  invariants), `tilings` (flat tilings + the `ARCH_TILINGS` registry and
  `_ArchTemplate` system), `aperiodic` (Penrose, Hat), `solids` (sphere,
  fullerenes, cube, tetrahedron, frames), `surfaces` (donut/cylinder/
  Möbius wrapping via shared immersion helpers), `catalog` (the menu,
  **derived** from `SURFACE_SPECS`/`TILING_SPECS`), `presets`
  (`ARCH_PRESETS` + `build_board`). The eight non-regular Archimedean
  tilings (six with two tile shapes, plus 3.4.6.4 and 4.6.12 with three)
  and their eight Laves (dual/Catalan) duals — built mechanically by
  `_dual_template` — wrap onto the donut/cylinder/Möbius via
  `_ArchTemplate` (one rectangular periodic domain + modular seam gluing;
  snub hexagonal and its dual the floret pentagonal are chiral, so no
  Möbius). The menu has two parallel tiling groups: **Uniform tilings**
  (the 11 uniform tilings) and **Dual-uniform tilings** (their 11 duals;
  the three regular tilings are self/mutually dual, so they appear in
  both). **To add a tiling or surface, see `AGENTS.md`** — a tiling is
  one `ARCH_TILINGS` + one `ARCH_PRESETS` row (duals also list their key
  in `catalog.DUAL_TILINGS`), a surface is one `SurfaceSpec` + an
  immersion + a wrap builder; the menu, mode strings, `MODES_3D`, and
  chirality gating all derive from those registries.
  Board-shape convention (applies to all future flat boards): a finite
  flat board should read as a roughly *square* rectangle, not a round
  disc, and a symmetric tiling should give a symmetric board. For periodic
  tilings take a rectangular window of whole periods centred on a rotation
  centre (`archimedean_board` keeps an `nx`×`ny` domain block of the
  `_ArchTemplate` centred on the tiling's biggest tile, so the window maps
  onto itself under the tiling's point group); for aperiodic ones
  (`penrose_board`, `hat_board`) grow generously and trim to the `keep`
  centremost cells by Chebyshev distance (`max(|dx|, |dy|)`). See the
  `AGENT NOTE` in `boards/tilings.py`.
- `minesweeper/gui.py` — pygame UI. `MenuScreen` (group → tiling →
  surface pages), `GameScreen` (flat), `GameScreen3D` (orthographic
  projection, back-face culling or two-sided, depth sort, drag to
  rotate). Everything is drawn on a canvas at `UI_SCALE`(=2)× and
  smooth-downscaled to the window each frame (supersampling); `App`
  scales mouse events up to canvas coordinates. Screens and tests work
  in canvas coordinates only.

## Run

```sh
.venv/bin/python -m minesweeper                 # menu
.venv/bin/python -m minesweeper --mode hexhex   # skip menu; see MODE_LABELS
```

The venv already has everything; recreate with `make venv`.
Dependency groups in pyproject.toml: `web` (pygbag), `test` (pytest,
ruff), `all` (both); locked to requirements[-web|-test|-all].txt by
`make lock` (uv). The Makefile wraps all common commands (`make help`);
CI runs `make test`/`make lint`, Pages deploys `make web-package`.

## Web build (pygbag)

`main.py` is the browser entry point; the game loop is async
(`App.run_async`) so pygbag can yield to the browser each frame.
`.github/workflows/deploy-pages.yml` builds and deploys to GitHub Pages
on every push to master. Browser-specific care in the code: no plain
`import pygame.gfxdraw` (pygbag's scanner would search PyPI for it;
gfxdraw doesn't exist in wasm at all — `_GFX` fallbacks in gui.py),
pygame key constants read via `getattr` at module level, and `main.py`
must import pygame itself so pygbag provisions the wasm wheel.

On the web the framebuffer and canvas CSS box fill the visible viewport
(`_WebPresenter`, using `visualViewport` so the mobile address bar is
excluded; set on every frame since pygbag's template only sizes the
canvas once at boot). The current screen is drawn on its own canvas, then
scaled by a factor fixed by the window width and the screen's
`web_ref_width` — not by how big the current board happens to be, so
boards keep one constant scale as you switch between them (the menu
reports its own width, so it fills the window edge to edge) — then
centred horizontally, with the background filling the rest. So there are
no letterbox gaps on a tall phone and switching boards does not resize
the UI; a screen wider or taller than the window is clamped down to stay
fully visible. The presenter also hands each screen extra height
(`set_viewport_height`) to fill the window, and the screen distributes
it: a game keeps the header at the top and centres the board in the space
below; the menu keeps the title at the top, drops the difficulty row to
the bottom and centres the mode list between them. The desktop leaves the
height at each screen's natural size, so its layout is unchanged. pygbag
also regenerates its default favicon on every build, so `make
web-package` overwrites it afterwards with scripts/make_favicon.py (the
in-game mine-in-hexagon icon).

Local test — must use pygbag's own server; on any other port the
template rewrites the CDN to localhost:8000 and pygame fails to load:

```sh
make web-run   # builds, then serves at http://localhost:8000
```

## Tests

```sh
.venv/bin/pytest            # full suite, sub-second
```

GUI tests run headless (SDL dummy driver, set in tests/test_gui.py).

### Claude Code on the web (cloud sessions)

`.claude/hooks/session-start.sh` (registered in `.claude/settings.json`)
provisions `.venv` (Python 3.13, per `.python-version`) and installs
`requirements-test.txt` at session start, so `make test`/`make lint` work
without manual setup. It runs only when `CLAUDE_CODE_REMOTE=true`. Test
deps come from PyPI, which is reachable from cloud sessions.

## Screenshots (headless)

```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
from minesweeper.gui import FontCache, make_screen

pygame.init()
pygame.display.set_mode((1, 1))
screen = make_screen("hexhex", "easy")   # or MenuScreen()
surface = pygame.Surface(screen.size)
screen.draw(surface, FontCache())
pygame.image.save(surface, "shot.png")
```

Note: the saved image is the 2x supersampled canvas; the real window
shows it downscaled by `UI_SCALE`. To preview what the user sees,
`pygame.transform.smoothscale` it to half size first.

## Pull requests

When a PR adds a new level/board or changes the UI, include a screenshot
of the result in the PR description. Generate it locally and headless
(see "Screenshots" above, smooth-scaled to half size to match what the
user sees) and attach it to the PR description — do not commit PR
screenshots to `docs/screenshots/` (that folder holds only the curated
README shots).
