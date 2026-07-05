"""Terminal interface for minesweeper."""

from __future__ import annotations

import argparse
import sys

from minesweeper.game import CellState, Game, GameState

DIFFICULTIES = {
    "easy": (9, 9, 10),
    "medium": (16, 16, 40),
    "hard": (16, 30, 99),
}

MINE = "*"
FLAG = "F"
HIDDEN = "."


def render(game: Game, *, reveal_mines: bool = False) -> str:
    header = "    " + " ".join(f"{c:>2}" for c in range(game.cols))
    lines = [header]
    for r in range(game.rows):
        cells = []
        for c in range(game.cols):
            state = game.cell_state(r, c)
            if state is CellState.FLAGGED:
                cells.append(FLAG)
            elif state is CellState.REVEALED:
                if game.is_mine(r, c):
                    cells.append(MINE)
                else:
                    n = game.adjacent_mines(r, c)
                    cells.append(str(n) if n else " ")
            elif reveal_mines and game.is_mine(r, c):
                cells.append(MINE)
            else:
                cells.append(HIDDEN)
        lines.append(f"{r:>3} " + " ".join(f"{cell:>2}" for cell in cells))
    return "\n".join(lines)


def parse_command(line: str) -> tuple[str, int, int] | None:
    """Parse a command line into (action, row, col).

    Accepts ``r ROW COL`` / ``reveal ROW COL``, ``f ROW COL`` / ``flag``,
    ``c ROW COL`` / ``chord``. Returns None for anything malformed.
    """
    parts = line.split()
    if len(parts) != 3:
        return None
    action = parts[0].lower()
    aliases = {"r": "r", "reveal": "r", "f": "f", "flag": "f", "c": "c", "chord": "c"}
    if action not in aliases:
        return None
    try:
        row, col = int(parts[1]), int(parts[2])
    except ValueError:
        return None
    return aliases[action], row, col


def play(game: Game) -> None:
    print("Commands: r ROW COL (reveal), f ROW COL (flag), c ROW COL (chord), q (quit)")
    while game.state is GameState.PLAYING:
        print()
        print(render(game))
        print(f"Flags remaining: {game.flags_remaining}")
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if line.lower() in ("q", "quit", "exit"):
            return
        command = parse_command(line)
        if command is None:
            print("Invalid command. Example: r 3 4")
            continue
        action, row, col = command
        if not game.in_bounds(row, col):
            print(f"Out of bounds: row 0-{game.rows - 1}, col 0-{game.cols - 1}")
            continue
        if action == "r":
            game.reveal(row, col)
        elif action == "f":
            game.toggle_flag(row, col)
        elif action == "c":
            game.chord(row, col)

    print()
    print(render(game, reveal_mines=True))
    if game.state is GameState.WON:
        print("You win!")
    else:
        print("Boom! You hit a mine.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minesweeper", description="Play minesweeper in the terminal.")
    parser.add_argument(
        "difficulty",
        nargs="?",
        choices=sorted(DIFFICULTIES),
        default="easy",
        help="board preset (default: easy)",
    )
    args = parser.parse_args(argv)
    rows, cols, mines = DIFFICULTIES[args.difficulty]
    play(Game(rows, cols, mines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
