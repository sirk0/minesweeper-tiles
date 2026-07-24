# Minesweeper (pygame)

A minesweeper clone with flat and 3D boards (sphere, fullerenes, cube,
tetrahedron, donut, Möbius strip, cylinder, Klein bottle). Python 3.13
(see `.python-version`), only dependency: `pygame-ce`.

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
  Möbius/Klein-bottle wrapping via shared immersion helpers), `catalog`
  (the menu, **derived** from `SURFACE_SPECS`/`TILING_SPECS`), `presets`
  (`ARCH_PRESETS` + `build_board`). The eight non-regular Archimedean
  tilings (six with two tile shapes, plus 3.4.6.4 and 4.6.12 with three)
  and their eight Laves (dual/Catalan) duals — built mechanically by
  `_dual_template` — wrap onto the donut/cylinder/Möbius/Klein-bottle via
  `_ArchTemplate` (one rectangular periodic domain + modular seam gluing;
  snub hexagonal and its dual the floret pentagonal are chiral, so no
  Möbius and no Klein bottle — both seams reverse orientation). The
  Klein bottle glues like the donut but flips the tube across the ring
  seam (the same `template.mirror` the Möbius uses); the
  self-intersecting bottle immersion hides some cells behind the neck, so
  every Klein board carries a `cell_cycle` the UI scrolls along to bring
  them into view. In the menu's shared tiling picker the three regular
  tilings show directly, then the **Uniform tilings** (the eight
  non-regular uniform tilings, `vertex_transitive=True` in `ARCH_TILINGS`)
  and **Dual-uniform tilings** (their eight Laves duals) open as submenus.
  **To add a tiling or surface, see `AGENTS.md`** — a tiling is
  one `ARCH_TILINGS` + one `ARCH_PRESETS` row (its uniform/dual family
  membership follows from `vertex_transitive`, no menu edit needed), a
  surface is one `SurfaceSpec` + an immersion + a wrap builder; the menu,
  mode strings, `MODES_3D`, and chirality gating all derive from those
  registries.
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
- `minesweeper/gui.py` — pygame UI. `MenuScreen` (a geometry-first home
  page — Classic / Flat / Flat manifolds / Sphere / Other. Classic launches
  flat squares; Flat and each flat manifold (plane, cylinder, Möbius, Klein,
  torus) open a shared tiling picker — regular tilings, uniform/dual family
  submenus, aperiodic (plane only), and a random option — parameterised by
  the surface it was reached through; Sphere and Other list their finished
  boards. Navigation is a `path` breadcrumb driven by the `MENU_ROOT`/
  `MANIFOLD_*`/`FAMILY_*`/`SPHERE_MODES`/`OTHER_MODES` tables in `catalog`),
  `GameScreen` (flat), `GameScreen3D` (orthographic
  projection, back-face culling or two-sided, depth sort, drag to
  rotate). Everything is drawn on a canvas at `UI_SCALE`(=2)× and
  smooth-downscaled to the window each frame (supersampling); `App`
  scales mouse events up to canvas coordinates. Screens and tests work
  in canvas coordinates only.

## Run

```sh
.venv/bin/python -m minesweeper                 # menu
.venv/bin/python -m minesweeper --mode hexhex   # skip menu; see MODE_LABELS
.venv/bin/python -m minesweeper --theme neumorph # UI theme; see THEMES in gui.py
```

The chrome (menu screen + buttons + header controls, not the board tiles)
is themeable: `THEMES`/`set_theme` in `gui.py` hold the light presets
(`flat` is the default; also `neumorph`, `ios`, `glass`, `paper`, and the
retro `classic`). Pick one with `--theme` or `MINESWEEPER_THEME`.

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
scaled by the ratio of the window width to the screen's `web_ref_width`.
Every screen reports its own width there (a game board its natural
width), so boards and the menu all fill the window edge to edge; a
screen taller than the window is clamped down to stay fully visible, so
there are never letterbox gaps on a tall phone. On a portrait viewport
(a phone held upright — `is_portrait`, plumbed through
`set_portrait`) a clearly landscape flat board (width > 1.2× height,
i.e. the classic 30×16 hard board) is drawn turned a quarter-turn
(`GameScreen._rotated`) so it fills the width; the desktop presenter
never reports portrait, so desktop and landscape windows keep boards as
designed. Cell size still varies per board, but the header controls do
not: the header row (back and flag-mode at the left edge, mine counter /
smiley / timer centred, Klein scroll arrows at the right edge) is laid
out at `_header_scale = board width / HEADER_REF_W`, which shrinks it to
fit boards narrower than `HEADER_REF_W` and, on the web only, grows it
(band height included, `_header_height`) on wider boards — because the
web scale is width-proportional, that keeps the controls one constant
touchable physical size across **all** boards. The desktop clamps the
scale at 1 so wide boards keep the normal-size header. The presenter also hands each screen extra height
(`set_viewport_height`) to fill the window, and the screen distributes
it: a game keeps the header at the top and centres the board in the space
below; the menu keeps the title at the top, drops the difficulty row to
the bottom and centres the mode list between them. The desktop leaves the
height at each screen's natural size, so its layout is unchanged. pygbag
also regenerates its default favicon and `index.html` on every build, so
`make web-package` runs scripts/make_web_icons.py afterwards: it
overwrites the favicon with the in-game mine-in-hexagon icon, writes an
`apple-touch-icon.png` (the same icon rendered full-bleed so iOS's own
rounded-square mask makes the iPhone home-screen icon match the macOS
dock), and injects the `apple-touch-icon` <link> that pygbag's template
omits (without it iOS shows a screenshot of the page instead of the app
icon).

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

## TypeScript app (`web/`)

The in-progress TypeScript/Three.js rewrite lives in `web/` and shares its
config and conformance oracle with the Python game through `data/*.json`
(see AGENTS.md). Commands (`npm run typecheck/test/build`, Playwright
`e2e`) and — important when changing anything visual or interactive —
**how to drive and screenshot the app headless, plus the gotchas that
actually bite** (the `window.__ms` seam, flood-fill devouring sparse mine
fixtures, `--update-snapshots` silently keeping baselines that pass within
tolerance, ESM script placement) are documented in `web/README.md` under
"Agent notes". Verify UI changes by looking at real screenshots, not just
by the test suite passing.

## Pull requests

When a PR adds a new level/board or changes the UI, include a screenshot
of the result in the PR description. Generate it locally and headless
(see "Screenshots" above, smooth-scaled to half size to match what the
user sees) and attach it to the PR description — do not commit PR
screenshots to `docs/screenshots/` (that folder holds only the curated
README shots).
