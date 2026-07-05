import random

import pytest

from minesweeper.game import CellState, Game, GameState


def make_game(mines={(0, 0)}, rows=4, cols=4):
    """4x4 game with explicit mine placement for deterministic tests."""
    return Game(rows, cols, len(mines), mine_positions=set(mines))


class TestConstruction:
    def test_valid_game(self):
        game = Game(9, 9, 10)
        assert game.rows == 9
        assert game.cols == 9
        assert game.mine_count == 10
        assert game.state is GameState.PLAYING

    def test_all_cells_start_hidden(self):
        game = Game(3, 3, 1)
        assert all(
            game.cell_state(r, c) is CellState.HIDDEN
            for r in range(3)
            for c in range(3)
        )

    @pytest.mark.parametrize("rows,cols,mines", [(0, 5, 1), (5, 0, 1), (-1, 5, 1)])
    def test_rejects_invalid_dimensions(self, rows, cols, mines):
        with pytest.raises(ValueError):
            Game(rows, cols, mines)

    def test_rejects_zero_mines(self):
        with pytest.raises(ValueError):
            Game(5, 5, 0)

    def test_rejects_too_many_mines(self):
        with pytest.raises(ValueError):
            Game(3, 3, 9)

    def test_rejects_out_of_bounds_mine_positions(self):
        with pytest.raises(ValueError):
            Game(3, 3, 1, mine_positions={(5, 5)})


class TestMinePlacement:
    def test_places_exact_mine_count(self):
        game = Game(9, 9, 10, rng=random.Random(42))
        game.reveal(4, 4)
        mines = sum(
            1 for r in range(9) for c in range(9) if game.is_mine(r, c)
        )
        assert mines == 10

    def test_first_reveal_is_never_a_mine(self):
        for seed in range(50):
            game = Game(5, 5, 24, rng=random.Random(seed))
            game.reveal(2, 3)
            assert not game.is_mine(2, 3)
            assert game.state is not GameState.LOST

    def test_explicit_mine_positions_are_used(self):
        game = make_game(mines={(1, 1), (2, 2)})
        assert game.is_mine(1, 1)
        assert game.is_mine(2, 2)
        assert not game.is_mine(0, 0)


class TestAdjacency:
    def test_counts_adjacent_mines(self):
        game = make_game(mines={(0, 0), (0, 1), (1, 0)})
        assert game.adjacent_mines(1, 1) == 3
        assert game.adjacent_mines(0, 2) == 1
        assert game.adjacent_mines(3, 3) == 0

    def test_corner_has_three_neighbors(self):
        game = make_game()
        assert len(game.neighbors(0, 0)) == 3
        assert len(game.neighbors(3, 3)) == 3

    def test_center_has_eight_neighbors(self):
        game = make_game()
        assert len(game.neighbors(1, 1)) == 8


class TestReveal:
    def test_reveal_safe_cell(self):
        game = make_game(mines={(0, 0), (0, 2)})
        game.reveal(0, 1)
        assert game.cell_state(0, 1) is CellState.REVEALED
        assert game.state is GameState.PLAYING

    def test_reveal_mine_loses(self):
        game = make_game(mines={(0, 0), (3, 3)})
        game.reveal(1, 1)  # trigger placement via first safe reveal
        game.reveal(0, 0)
        assert game.state is GameState.LOST
        assert game.cell_state(0, 0) is CellState.REVEALED

    def test_zero_cell_flood_fills(self):
        # Single mine in the corner: revealing the far corner should open
        # every cell except the mine.
        game = make_game(mines={(0, 0)})
        game.reveal(3, 3)
        revealed = sum(
            1
            for r in range(4)
            for c in range(4)
            if game.cell_state(r, c) is CellState.REVEALED
        )
        assert revealed == 15
        assert game.cell_state(0, 0) is not CellState.REVEALED

    def test_flood_fill_stops_at_numbers(self):
        # Mines across row 2 wall off row 3 from rows 0-1.
        game = make_game(mines={(2, 0), (2, 1), (2, 2), (2, 3)})
        game.reveal(0, 0)
        assert game.cell_state(0, 0) is CellState.REVEALED
        assert game.cell_state(1, 1) is CellState.REVEALED  # number boundary
        assert game.cell_state(3, 0) is CellState.HIDDEN  # beyond the wall

    def test_reveal_flagged_cell_is_noop(self):
        game = make_game()
        game.toggle_flag(2, 2)
        game.reveal(2, 2)
        assert game.cell_state(2, 2) is CellState.FLAGGED

    def test_reveal_out_of_bounds_is_noop(self):
        game = make_game()
        game.reveal(99, 99)  # must not raise
        assert game.state is GameState.PLAYING

    def test_reveal_after_loss_is_noop(self):
        game = make_game(mines={(0, 0)})
        game.reveal(0, 0)
        assert game.state is GameState.LOST
        game.reveal(3, 3)
        assert game.cell_state(3, 3) is CellState.HIDDEN


class TestFlag:
    def test_toggle_flag_on_and_off(self):
        game = make_game()
        game.toggle_flag(1, 1)
        assert game.cell_state(1, 1) is CellState.FLAGGED
        game.toggle_flag(1, 1)
        assert game.cell_state(1, 1) is CellState.HIDDEN

    def test_cannot_flag_revealed_cell(self):
        game = make_game(mines={(0, 0)})
        game.reveal(3, 3)
        game.toggle_flag(3, 3)
        assert game.cell_state(3, 3) is CellState.REVEALED

    def test_flags_remaining_counter(self):
        game = make_game(mines={(0, 0), (1, 1)})
        assert game.flags_remaining == 2
        game.toggle_flag(0, 0)
        assert game.flags_remaining == 1
        game.toggle_flag(3, 3)
        assert game.flags_remaining == 0
        game.toggle_flag(3, 3)
        assert game.flags_remaining == 1


class TestWin:
    def test_revealing_all_safe_cells_wins(self):
        game = make_game(mines={(0, 0)})
        game.reveal(3, 3)  # flood fill opens everything but the mine
        assert game.state is GameState.WON

    def test_win_on_last_individual_reveal(self):
        # Mines wall off (3,0) so it needs its own reveal after the flood.
        game = make_game(mines={(2, 0), (2, 1), (3, 1)})
        game.reveal(0, 3)
        assert game.state is GameState.PLAYING
        game.reveal(3, 0)
        assert game.state is GameState.WON

    def test_no_win_while_safe_cells_remain(self):
        game = make_game(mines={(0, 0), (2, 2)})
        game.reveal(0, 1)
        assert game.state is GameState.PLAYING


class TestChord:
    def test_chord_reveals_unflagged_neighbors(self):
        game = make_game(mines={(0, 0)})
        game.reveal(1, 1)  # shows "1"
        game.toggle_flag(0, 0)
        game.chord(1, 1)
        for r, c in game.neighbors(1, 1):
            if (r, c) != (0, 0):
                assert game.cell_state(r, c) is CellState.REVEALED

    def test_chord_without_matching_flags_is_noop(self):
        game = make_game(mines={(0, 0)})
        game.reveal(1, 1)
        game.chord(1, 1)  # no flags placed
        assert game.cell_state(0, 1) is CellState.HIDDEN

    def test_chord_on_hidden_cell_is_noop(self):
        game = make_game(mines={(0, 0)})
        game.chord(2, 2)
        assert game.cell_state(2, 2) is CellState.HIDDEN

    def test_chord_with_wrong_flag_hits_mine(self):
        game = make_game(mines={(0, 0)})
        game.reveal(1, 1)
        game.toggle_flag(0, 1)  # wrong guess
        game.chord(1, 1)
        assert game.state is GameState.LOST
