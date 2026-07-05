"""Core minesweeper game logic, independent of any user interface."""

from __future__ import annotations

import random
from enum import Enum


class CellState(Enum):
    HIDDEN = "hidden"
    REVEALED = "revealed"
    FLAGGED = "flagged"


class GameState(Enum):
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


class Game:
    """A single minesweeper game on a rows x cols board.

    Mines are placed lazily on the first reveal so the first click is
    always safe. Deterministic behaviour for tests is available either by
    passing an explicit ``mine_positions`` set or a seeded ``rng``.
    """

    def __init__(
        self,
        rows: int,
        cols: int,
        mine_count: int,
        *,
        mine_positions: set[tuple[int, int]] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("board must be at least 1x1")
        self.rows = rows
        self.cols = cols
        if mine_positions is not None:
            for pos in mine_positions:
                if not self.in_bounds(*pos):
                    raise ValueError(f"mine position {pos} out of bounds")
            mine_count = len(mine_positions)
        if mine_count < 1:
            raise ValueError("need at least one mine")
        if mine_count >= rows * cols:
            raise ValueError("mine count must leave at least one safe cell")

        self.mine_count = mine_count
        self.state = GameState.PLAYING
        self._rng = rng if rng is not None else random.Random()
        self._mines: set[tuple[int, int]] = set(mine_positions or ())
        self._mines_placed = mine_positions is not None
        self._cell_states = [
            [CellState.HIDDEN for _ in range(cols)] for _ in range(rows)
        ]
        self._revealed_count = 0

    # -- geometry ---------------------------------------------------------

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def neighbors(self, row: int, col: int) -> list[tuple[int, int]]:
        result = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                if self.in_bounds(row + dr, col + dc):
                    result.append((row + dr, col + dc))
        return result

    # -- queries ----------------------------------------------------------

    def cell_state(self, row: int, col: int) -> CellState:
        return self._cell_states[row][col]

    def is_mine(self, row: int, col: int) -> bool:
        return (row, col) in self._mines

    def adjacent_mines(self, row: int, col: int) -> int:
        return sum(1 for pos in self.neighbors(row, col) if pos in self._mines)

    @property
    def flags_remaining(self) -> int:
        flagged = sum(
            1
            for row in self._cell_states
            for state in row
            if state is CellState.FLAGGED
        )
        return self.mine_count - flagged

    # -- moves ------------------------------------------------------------

    def reveal(self, row: int, col: int) -> None:
        """Reveal a cell. Ends the game if it is a mine; flood-fills if it
        has no adjacent mines. No-op on flagged/revealed cells or after the
        game has ended."""
        if self.state is not GameState.PLAYING or not self.in_bounds(row, col):
            return
        if self._cell_states[row][col] is not CellState.HIDDEN:
            return

        if not self._mines_placed:
            self._place_mines(safe=(row, col))

        if (row, col) in self._mines:
            self._cell_states[row][col] = CellState.REVEALED
            self.state = GameState.LOST
            return

        self._flood_reveal(row, col)
        if self._revealed_count == self.rows * self.cols - self.mine_count:
            self.state = GameState.WON

    def toggle_flag(self, row: int, col: int) -> None:
        if self.state is not GameState.PLAYING or not self.in_bounds(row, col):
            return
        current = self._cell_states[row][col]
        if current is CellState.HIDDEN:
            self._cell_states[row][col] = CellState.FLAGGED
        elif current is CellState.FLAGGED:
            self._cell_states[row][col] = CellState.HIDDEN

    def chord(self, row: int, col: int) -> None:
        """Reveal all unflagged neighbors of a revealed number cell whose
        flag count matches its adjacent mine count."""
        if self.state is not GameState.PLAYING or not self.in_bounds(row, col):
            return
        if self._cell_states[row][col] is not CellState.REVEALED:
            return
        neighbors = self.neighbors(row, col)
        flagged = sum(
            1 for r, c in neighbors if self._cell_states[r][c] is CellState.FLAGGED
        )
        if flagged != self.adjacent_mines(row, col):
            return
        for r, c in neighbors:
            if self._cell_states[r][c] is CellState.HIDDEN:
                self.reveal(r, c)
                if self.state is not GameState.PLAYING:
                    return

    # -- internals --------------------------------------------------------

    def _place_mines(self, safe: tuple[int, int]) -> None:
        candidates = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) != safe
        ]
        self._mines = set(self._rng.sample(candidates, self.mine_count))
        self._mines_placed = True

    def _flood_reveal(self, row: int, col: int) -> None:
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if self._cell_states[r][c] is not CellState.HIDDEN:
                continue
            self._cell_states[r][c] = CellState.REVEALED
            self._revealed_count += 1
            if self.adjacent_mines(r, c) == 0:
                stack.extend(self.neighbors(r, c))
