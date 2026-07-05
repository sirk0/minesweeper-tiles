# Minesweeper

A minesweeper clone in Python (pygame) with four board geometries:

- **Classic squares** — the traditional grid (8 neighbors)
- **Triangle of triangles** — a big triangle subdivided into small
  triangles (12 neighbors)
- **Triangle grid** — a rectangular surface tiled with triangles
  (12 neighbors)
- **Hexagon grid** — a surface tiled with hexagons (6 neighbors)

## Play

```sh
pip install pygame-ce
python3 -m minesweeper
```

A menu screen picks the board mode and difficulty. In game:

- **Left-click** — reveal a cell (the first reveal is always safe);
  left-click a revealed number to chord
- **Right-click** — toggle a flag
- **Face button** or `n` — new game
- `1` / `2` / `3` — switch to easy / medium / hard
- `Escape` — back to the menu

`python3 -m minesweeper --mode hex [difficulty]` skips the menu.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install pytest pygame-ce
.venv/bin/pytest
```

Tests run headless via SDL's dummy video driver.

Code layout: `minesweeper/game.py` holds the rules over an arbitrary
cell graph; `minesweeper/boards.py` generates the tilings (cells are
polygons on an integer lattice — two cells are neighbors when they
share a lattice vertex); `minesweeper/gui.py` is the pygame interface.
