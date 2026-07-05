# Minesweeper

A terminal minesweeper clone in pure Python (no runtime dependencies).

## Play

```sh
python3 -m minesweeper          # easy: 9x9, 10 mines
python3 -m minesweeper medium   # 16x16, 40 mines
python3 -m minesweeper hard     # 16x30, 99 mines
```

Commands at the prompt:

- `r ROW COL` — reveal a cell (the first reveal is always safe)
- `f ROW COL` — toggle a flag
- `c ROW COL` — chord: reveal neighbors of a satisfied number
- `q` — quit

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/pytest
```

Game rules live in `minesweeper/game.py` (UI-independent); the terminal
interface is in `minesweeper/cli.py`.
