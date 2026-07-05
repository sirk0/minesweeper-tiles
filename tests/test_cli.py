from minesweeper.cli import DIFFICULTIES, parse_command, render
from minesweeper.game import Game, GameState


class TestParseCommand:
    def test_reveal_short_and_long(self):
        assert parse_command("r 3 4") == ("r", 3, 4)
        assert parse_command("reveal 3 4") == ("r", 3, 4)

    def test_flag_and_chord(self):
        assert parse_command("f 0 0") == ("f", 0, 0)
        assert parse_command("FLAG 1 2") == ("f", 1, 2)
        assert parse_command("c 2 2") == ("c", 2, 2)

    def test_rejects_malformed_input(self):
        assert parse_command("") is None
        assert parse_command("r 3") is None
        assert parse_command("r 3 4 5") is None
        assert parse_command("x 3 4") is None
        assert parse_command("r three four") is None


class TestRender:
    def test_hidden_board(self):
        game = Game(2, 2, 1, mine_positions={(0, 0)})
        output = render(game)
        assert output.count(".") == 4
        assert "*" not in output

    def test_revealed_numbers_and_blanks(self):
        game = Game(3, 3, 1, mine_positions={(0, 0)})
        game.reveal(2, 2)  # flood fill
        output = render(game)
        assert "1" in output  # cells adjacent to the mine
        assert "." in output  # the mine cell stays hidden

    def test_flag_marker(self):
        game = Game(2, 2, 1, mine_positions={(0, 0)})
        game.toggle_flag(1, 1)
        assert "F" in render(game)

    def test_reveal_mines_shows_mines(self):
        game = Game(2, 2, 1, mine_positions={(0, 0)})
        assert "*" in render(game, reveal_mines=True)


class TestDifficulties:
    def test_presets_are_playable(self):
        for rows, cols, mines in DIFFICULTIES.values():
            game = Game(rows, cols, mines)
            game.reveal(rows // 2, cols // 2)
            assert game.state is not GameState.LOST  # first click is safe
            assert not game.is_mine(rows // 2, cols // 2)
