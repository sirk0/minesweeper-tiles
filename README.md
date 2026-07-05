# Minesweeper

A minesweeper clone in Python (pygame) with six board geometries:

- **Classic squares** — the traditional grid (8 neighbors)
- **Triangle of triangles** — a big triangle subdivided into small
  triangles (12 neighbors)
- **Triangle grid** — a rectangular surface tiled with triangles
  (12 neighbors)
- **Hexagon grid** — a surface tiled with hexagons (6 neighbors)
- **Pentagon sphere (3D)** — a sphere tiled with 60 pentagons, a
  pentagonal hexecontahedron (7 neighbors)
- **Square donut (3D)** — a torus tiled with quadrilaterals; the grid
  wraps around, so every cell has 8 neighbors and there are no edges

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

On 3D boards, **drag** with the left button (or use the arrow keys) to
rotate the surface; a short click reveals.

`python3 -m minesweeper --mode hex [difficulty]` skips the menu.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install pytest pygame-ce
.venv/bin/pytest
```

Tests run headless via SDL's dummy video driver.

Code layout: `minesweeper/game.py` holds the rules over an arbitrary
cell graph; `minesweeper/boards.py` generates the tilings (cell
vertices get exact hashable ids — lattice points in 2D, symbolic keys
in 3D — and two cells are neighbors when they share a vertex); the
sphere is built with the Conway gyro operation on an icosahedron;
`minesweeper/gui.py` is the pygame interface, including the rotatable
orthographic 3D view.
