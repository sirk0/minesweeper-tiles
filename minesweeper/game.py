"""Core minesweeper rules over an arbitrary cell graph.

The board is described by an adjacency mapping ``cell -> neighbors``;
cells can be any hashable ids. Board geometry (squares, triangles,
hexagons, ...) lives in :mod:`minesweeper.boards`.
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Hashable, Iterable, Mapping

Cell = Hashable


class CellState(Enum):
    HIDDEN = "hidden"
    REVEALED = "revealed"
    FLAGGED = "flagged"


class GameState(Enum):
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


class Game:
    """A single minesweeper game on an arbitrary board.

    Mines are placed lazily on the first reveal so the first click is
    always safe. Deterministic behaviour for tests is available either by
    passing an explicit ``mine_positions`` set or a seeded ``rng``.
    """

    def __init__(
        self,
        adjacency: Mapping[Cell, Iterable[Cell]],
        mine_count: int | None = None,
        *,
        mine_positions: set[Cell] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._adjacency = {
            cell: tuple(neighbors) for cell, neighbors in adjacency.items()
        }
        if not self._adjacency:
            raise ValueError("board has no cells")
        for cell, neighbors in self._adjacency.items():
            for neighbor in neighbors:
                if neighbor not in self._adjacency:
                    raise ValueError(
                        f"neighbor {neighbor!r} of {cell!r} is not a board cell"
                    )
        if mine_positions is not None:
            unknown = set(mine_positions) - self._adjacency.keys()
            if unknown:
                raise ValueError(f"mine positions not on the board: {unknown!r}")
            mine_count = len(mine_positions)
        if mine_count is None or mine_count < 1:
            raise ValueError("need at least one mine")
        if mine_count >= len(self._adjacency):
            raise ValueError("mine count must leave at least one safe cell")

        self.mine_count = mine_count
        self.state = GameState.PLAYING
        self._rng = rng if rng is not None else random.Random()
        self._mines: set[Cell] = set(mine_positions or ())
        self._mines_placed = mine_positions is not None
        self._cell_states = {cell: CellState.HIDDEN for cell in self._adjacency}
        self._revealed_count = 0

    # -- queries ----------------------------------------------------------

    @property
    def cells(self) -> tuple[Cell, ...]:
        return tuple(self._adjacency)

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        return self._adjacency[cell]

    def cell_state(self, cell: Cell) -> CellState:
        return self._cell_states[cell]

    def is_mine(self, cell: Cell) -> bool:
        return cell in self._mines

    def adjacent_mines(self, cell: Cell) -> int:
        return sum(1 for n in self._adjacency[cell] if n in self._mines)

    @property
    def flags_remaining(self) -> int:
        flagged = sum(
            1 for state in self._cell_states.values() if state is CellState.FLAGGED
        )
        return self.mine_count - flagged

    # -- moves ------------------------------------------------------------

    def reveal(self, cell: Cell) -> None:
        """Reveal a cell. Ends the game if it is a mine; flood-fills from
        cells with no adjacent mines. No-op on flagged/revealed/unknown
        cells or after the game has ended."""
        if self.state is not GameState.PLAYING or cell not in self._adjacency:
            return
        if self._cell_states[cell] is not CellState.HIDDEN:
            return

        if not self._mines_placed:
            self._place_mines(safe=cell)

        if cell in self._mines:
            self._cell_states[cell] = CellState.REVEALED
            self.state = GameState.LOST
            return

        self._flood_reveal(cell)
        if self._revealed_count == len(self._adjacency) - self.mine_count:
            self.state = GameState.WON
            # flag the remaining mines so the flag counter reads zero
            for mine in self._mines:
                if self._cell_states[mine] is CellState.HIDDEN:
                    self._cell_states[mine] = CellState.FLAGGED

    def toggle_flag(self, cell: Cell) -> None:
        if self.state is not GameState.PLAYING or cell not in self._adjacency:
            return
        current = self._cell_states[cell]
        if current is CellState.HIDDEN:
            self._cell_states[cell] = CellState.FLAGGED
        elif current is CellState.FLAGGED:
            self._cell_states[cell] = CellState.HIDDEN

    def chord(self, cell: Cell) -> None:
        """Reveal all unflagged neighbors of a revealed cell whose flag
        count matches its adjacent mine count."""
        if self.state is not GameState.PLAYING or cell not in self._adjacency:
            return
        if self._cell_states[cell] is not CellState.REVEALED:
            return
        neighbors = self._adjacency[cell]
        flagged = sum(
            1 for n in neighbors if self._cell_states[n] is CellState.FLAGGED
        )
        if flagged != self.adjacent_mines(cell):
            return
        for n in neighbors:
            if self._cell_states[n] is CellState.HIDDEN:
                self.reveal(n)
                if self.state is not GameState.PLAYING:
                    return

    # -- internals --------------------------------------------------------

    def _place_mines(self, safe: Cell) -> None:
        candidates = [cell for cell in self._adjacency if cell != safe]
        self._mines = set(self._rng.sample(candidates, self.mine_count))
        self._mines_placed = True

    def _flood_reveal(self, cell: Cell) -> None:
        stack = [cell]
        while stack:
            current = stack.pop()
            if self._cell_states[current] is not CellState.HIDDEN:
                continue
            self._cell_states[current] = CellState.REVEALED
            self._revealed_count += 1
            if self.adjacent_mines(current) == 0:
                stack.extend(self._adjacency[current])
