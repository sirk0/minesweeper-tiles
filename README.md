# Minesweeper

A minesweeper clone in Python (pygame). Pick a surface, then a tiling:

- **Flat surface** — classic squares (8 neighbors), a big triangle
  subdivided into small triangles (12), a triangle grid (12), hexagons
  (6), or a big hexagon composed of small hexagons (6)
- **Sphere (3D)** — 60 pentagons (a pentagonal hexecontahedron, 7
  neighbors) or a C80 fullerene (12 pentagons + 30 hexagons)
- **Donut (3D)** — quadrilaterals wrapping in both directions: every
  cell has 8 neighbors, there are no border cells
- **Möbius strip (3D)** — quadrilaterals on a one-sided surface; the
  strip glues to itself with a flip
- **Cylinder (3D)** — quadrilaterals around an open tube

## Play

```sh
pip install pygame-ce
python3 -m minesweeper
```

The menu picks a topology, then one of its tilings and a difficulty.
In game:

- **Left-click** — reveal a cell (the first reveal is always safe);
  left-click a revealed number to chord
- **Right-click** — toggle a flag
- **Face button** or `n` — new game
- `1` / `2` / `3` — switch to easy / medium / hard
- **`<` button** or `Escape` — back to the menu

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
