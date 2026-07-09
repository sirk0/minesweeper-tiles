# Minesweeper (pygame)

A minesweeper clone with flat and 3D boards (sphere, fullerenes, donut,
Möbius strip, cylinder). Python 3.14 (see `.python-version`), only dependency: `pygame-ce`.

## Architecture

- `minesweeper/game.py` — game rules over an arbitrary cell graph
  (`Game(adjacency, mine_count)`); knows nothing about geometry or UI.
- `minesweeper/boards.py` — board builders. Cells are polygons whose
  vertices have exact hashable ids (integer lattice points in 2D,
  symbolic/barycentric keys in 3D); two cells are neighbors when they
  share a vertex. Presets per mode/difficulty in `_PRESETS`;
  `TOPOLOGIES` groups modes for the menu.
- `minesweeper/gui.py` — pygame UI. `MenuScreen` (topology page →
  tiling page), `GameScreen` (flat), `GameScreen3D` (orthographic
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

The venv already has pygame-ce and pytest; recreate with
`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`.
Locked requirements files are generated from pyproject.toml with
`uv pip compile pyproject.toml [--extra dev] -o <file> --universal`.

## Web build (pygbag)

`main.py` is the browser entry point; the game loop is async
(`App.run_async`) so pygbag can yield to the browser each frame.
`.github/workflows/deploy-pages.yml` builds and deploys to GitHub Pages
on every push to master. Browser-specific care in the code: no plain
`import pygame.gfxdraw` (pygbag's scanner would search PyPI for it;
gfxdraw doesn't exist in wasm at all — `_GFX` fallbacks in gui.py),
pygame key constants read via `getattr` at module level, and `main.py`
must import pygame itself so pygbag provisions the wasm wheel.

Local test (must use pygbag's own server; on any other port the
template rewrites the CDN to localhost:8000 and pygame fails to load):

```sh
mkdir -p build/app && cp main.py build/app/ && cp -r minesweeper build/app/
.venv/bin/python -m pygbag --ume_block 0 build/app   # http://localhost:8000
```

## Tests

```sh
.venv/bin/pytest            # full suite, sub-second
```

GUI tests run headless (SDL dummy driver, set in tests/test_gui.py).

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
