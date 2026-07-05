# Minesweeper

A minesweeper clone in Python with a pygame GUI and a dependency-free
terminal mode.

## Play (GUI)

```sh
pip install pygame-ce
python3 -m minesweeper          # easy: 9x9, 10 mines
python3 -m minesweeper medium   # 16x16, 40 mines
python3 -m minesweeper hard     # 16x30, 99 mines
```

Controls:

- **Left-click** — reveal a cell (the first reveal is always safe);
  left-click a revealed number to chord
- **Right-click** — toggle a flag
- **Face button** or `n` — new game
- `1` / `2` / `3` — switch to easy / medium / hard
- `Escape` — quit

## Play (terminal)

Runs anywhere, no dependencies:

```sh
python3 -m minesweeper --cli [difficulty]
```

Commands at the prompt:

- `r ROW COL` — reveal a cell (the first reveal is always safe)
- `f ROW COL` — toggle a flag
- `c ROW COL` — chord: reveal neighbors of a satisfied number
- `q` — quit

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install pytest pygame-ce
.venv/bin/pytest
```

GUI tests run headless via SDL's dummy video driver and are skipped
automatically if pygame is not installed.

Game rules live in `minesweeper/game.py` (UI-independent); the terminal
interface is in `minesweeper/cli.py` and the pygame GUI in
`minesweeper/gui.py`.
