import random

import pytest

from minesweeper.boards import square_board
from minesweeper.game import CellState, Game, GameState


def make_game(mines={(0, 0)}, rows=4, cols=4):
    """Square-grid game with explicit mine placement for deterministic
    tests. Cells are (row, col) tuples."""
    board = square_board(rows, cols, 1)
    return Game(board.adjacency, mine_positions=set(mines))


class TestConstruction:
    def test_valid_game(self):
        game = Game(square_board(9, 9, 10).adjacency, 10)
        assert len(game.cells) == 81
        assert game.mine_count == 10
        assert game.state is GameState.PLAYING

    def test_all_cells_start_hidden(self):
        game = make_game()
        assert all(game.cell_state(cell) is CellState.HIDDEN for cell in game.cells)

    def test_rejects_empty_board(self):
        with pytest.raises(ValueError):
            Game({}, 1)

    def test_rejects_neighbor_that_is_not_a_cell(self):
        with pytest.raises(ValueError):
            Game({"a": ["b"]}, 1)

    def test_rejects_zero_mines(self):
        with pytest.raises(ValueError):
            Game(square_board(5, 5, 1).adjacency, 0)

    def test_rejects_too_many_mines(self):
        with pytest.raises(ValueError):
            Game(square_board(3, 3, 1).adjacency, 9)

    def test_rejects_mine_positions_off_the_board(self):
        with pytest.raises(ValueError):
            Game(square_board(3, 3, 1).adjacency, mine_positions={(5, 5)})


class TestMinePlacement:
    def test_places_exact_mine_count(self):
        game = Game(square_board(9, 9, 10).adjacency, 10, rng=random.Random(42))
        game.reveal((4, 4))
        assert sum(1 for cell in game.cells if game.is_mine(cell)) == 10

    def test_first_reveal_is_never_a_mine(self):
        adjacency = square_board(5, 5, 1).adjacency
        for seed in range(50):
            game = Game(adjacency, 24, rng=random.Random(seed))
            game.reveal((2, 3))
            assert not game.is_mine((2, 3))
            assert game.state is not GameState.LOST

    def test_explicit_mine_positions_are_used(self):
        game = make_game(mines={(1, 1), (2, 2)})
        assert game.is_mine((1, 1))
        assert game.is_mine((2, 2))
        assert not game.is_mine((0, 0))


class TestAdjacency:
    def test_counts_adjacent_mines(self):
        game = make_game(mines={(0, 0), (0, 1), (1, 0)})
        assert game.adjacent_mines((1, 1)) == 3
        assert game.adjacent_mines((0, 2)) == 1
        assert game.adjacent_mines((3, 3)) == 0

    def test_square_corner_has_three_neighbors(self):
        game = make_game()
        assert len(game.neighbors((0, 0))) == 3
        assert len(game.neighbors((3, 3))) == 3

    def test_square_center_has_eight_neighbors(self):
        game = make_game()
        assert len(game.neighbors((1, 1))) == 8


class TestReveal:
    def test_reveal_safe_cell(self):
        game = make_game(mines={(0, 0), (0, 2)})
        game.reveal((0, 1))
        assert game.cell_state((0, 1)) is CellState.REVEALED
        assert game.state is GameState.PLAYING

    def test_reveal_mine_loses(self):
        game = make_game(mines={(0, 0), (3, 3)})
        game.reveal((1, 1))
        game.reveal((0, 0))
        assert game.state is GameState.LOST
        assert game.cell_state((0, 0)) is CellState.REVEALED

    def test_zero_cell_flood_fills(self):
        # Single mine in the corner: revealing the far corner should open
        # every cell except the mine.
        game = make_game(mines={(0, 0)})
        game.reveal((3, 3))
        revealed = sum(
            1 for cell in game.cells if game.cell_state(cell) is CellState.REVEALED
        )
        assert revealed == 15
        assert game.cell_state((0, 0)) is not CellState.REVEALED

    def test_flood_fill_stops_at_numbers(self):
        # Mines across row 2 wall off row 3 from rows 0-1.
        game = make_game(mines={(2, 0), (2, 1), (2, 2), (2, 3)})
        game.reveal((0, 0))
        assert game.cell_state((0, 0)) is CellState.REVEALED
        assert game.cell_state((1, 1)) is CellState.REVEALED  # number boundary
        assert game.cell_state((3, 0)) is CellState.HIDDEN  # beyond the wall

    def test_reveal_flagged_cell_is_noop(self):
        game = make_game()
        game.toggle_flag((2, 2))
        game.reveal((2, 2))
        assert game.cell_state((2, 2)) is CellState.FLAGGED

    def test_reveal_unknown_cell_is_noop(self):
        game = make_game()
        game.reveal((99, 99))  # must not raise
        assert game.state is GameState.PLAYING

    def test_reveal_after_loss_is_noop(self):
        game = make_game(mines={(0, 0)})
        game.reveal((0, 0))
        assert game.state is GameState.LOST
        game.reveal((3, 3))
        assert game.cell_state((3, 3)) is CellState.HIDDEN


class TestFlag:
    def test_toggle_flag_on_and_off(self):
        game = make_game()
        game.toggle_flag((1, 1))
        assert game.cell_state((1, 1)) is CellState.FLAGGED
        game.toggle_flag((1, 1))
        assert game.cell_state((1, 1)) is CellState.HIDDEN

    def test_cannot_flag_revealed_cell(self):
        game = make_game(mines={(0, 0)})
        game.reveal((3, 3))
        game.toggle_flag((3, 3))
        assert game.cell_state((3, 3)) is CellState.REVEALED

    def test_flags_remaining_counter(self):
        game = make_game(mines={(0, 0), (1, 1)})
        assert game.flags_remaining == 2
        game.toggle_flag((0, 0))
        assert game.flags_remaining == 1
        game.toggle_flag((3, 3))
        assert game.flags_remaining == 0
        game.toggle_flag((3, 3))
        assert game.flags_remaining == 1


class TestWin:
    def test_revealing_all_safe_cells_wins(self):
        game = make_game(mines={(0, 0)})
        game.reveal((3, 3))  # flood fill opens everything but the mine
        assert game.state is GameState.WON

    def test_win_on_last_individual_reveal(self):
        # Mines wall off (3,0) so it needs its own reveal after the flood.
        game = make_game(mines={(2, 0), (2, 1), (3, 1)})
        game.reveal((0, 3))
        assert game.state is GameState.PLAYING
        game.reveal((3, 0))
        assert game.state is GameState.WON

    def test_no_win_while_safe_cells_remain(self):
        game = make_game(mines={(0, 0), (2, 2)})
        game.reveal((0, 1))
        assert game.state is GameState.PLAYING

    def test_win_auto_flags_mines_and_zeroes_counter(self):
        game = make_game(mines={(0, 0), (2, 2)})
        assert game.flags_remaining == 2
        for cell in game.cells:
            if cell not in {(0, 0), (2, 2)}:
                game.reveal(cell)
        assert game.state is GameState.WON
        assert game.cell_state((0, 0)) is CellState.FLAGGED
        assert game.cell_state((2, 2)) is CellState.FLAGGED
        assert game.flags_remaining == 0


class TestChord:
    def test_chord_reveals_unflagged_neighbors(self):
        game = make_game(mines={(0, 0)})
        game.reveal((1, 1))  # shows "1"
        game.toggle_flag((0, 0))
        game.chord((1, 1))
        for cell in game.neighbors((1, 1)):
            if cell != (0, 0):
                assert game.cell_state(cell) is CellState.REVEALED

    def test_chord_without_matching_flags_is_noop(self):
        game = make_game(mines={(0, 0)})
        game.reveal((1, 1))
        game.chord((1, 1))  # no flags placed
        assert game.cell_state((0, 1)) is CellState.HIDDEN

    def test_chord_on_hidden_cell_is_noop(self):
        game = make_game(mines={(0, 0)})
        game.chord((2, 2))
        assert game.cell_state((2, 2)) is CellState.HIDDEN

    def test_chord_with_wrong_flag_hits_mine(self):
        game = make_game(mines={(0, 0)})
        game.reveal((1, 1))
        game.toggle_flag((0, 1))  # wrong guess
        game.chord((1, 1))
        assert game.state is GameState.LOST


class TestNonSquareTopology:
    def test_game_works_on_arbitrary_graph(self):
        # A 4-cycle: each cell has two neighbors.
        adjacency = {0: (1, 3), 1: (0, 2), 2: (1, 3), 3: (2, 0)}
        game = Game(adjacency, mine_positions={0})
        game.reveal(2)  # opposite the mine: no adjacent mines, floods 1 and 3
        assert game.state is GameState.WON
        assert game.adjacent_mines(1) == 1
