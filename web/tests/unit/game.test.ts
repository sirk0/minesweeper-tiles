import { describe, expect, it } from "vitest";
import { Game } from "../../src/game";
import { mulberry32 } from "../../src/rng";
import { cid, type CellId } from "../../src/boards/core";
import { squareBoard } from "../../src/boards/tilings";

// Port of tests/test_game.py. Cells are "row,col" strings.
function makeGame(mines: [number, number][] = [[0, 0]], rows = 4, cols = 4): Game {
  const board = squareBoard(rows, cols, 1);
  return new Game(board.adjacency, {
    minePositions: mines.map(([r, c]) => cid(r, c)),
  });
}
const C = (r: number, c: number): CellId => cid(r, c);

describe("construction", () => {
  it("valid game", () => {
    const game = new Game(squareBoard(9, 9, 10).adjacency, { mineCount: 10 });
    expect(game.cells.length).toBe(81);
    expect(game.mineCount).toBe(10);
    expect(game.state).toBe("playing");
  });
  it("all cells start hidden", () => {
    const game = makeGame();
    expect(game.cells.every((c) => game.cellState(c) === "hidden")).toBe(true);
  });
  it("rejects empty board", () => {
    expect(() => new Game(new Map(), { mineCount: 1 })).toThrow();
  });
  it("rejects neighbor that is not a cell", () => {
    expect(() => new Game(new Map([["a", ["b"]]]), { mineCount: 1 })).toThrow();
  });
  it("rejects zero mines", () => {
    expect(() => new Game(squareBoard(5, 5, 1).adjacency, { mineCount: 0 })).toThrow();
  });
  it("rejects too many mines", () => {
    expect(() => new Game(squareBoard(3, 3, 1).adjacency, { mineCount: 9 })).toThrow();
  });
  it("rejects mine positions off the board", () => {
    expect(
      () => new Game(squareBoard(3, 3, 1).adjacency, { minePositions: [C(5, 5)] }),
    ).toThrow();
  });
});

describe("mine placement", () => {
  it("places exact mine count", () => {
    const game = new Game(squareBoard(9, 9, 10).adjacency, {
      mineCount: 10,
      rng: mulberry32(42),
    });
    game.reveal(C(4, 4));
    expect(game.cells.filter((c) => game.isMine(c)).length).toBe(10);
  });
  it("first reveal is never a mine", () => {
    const adjacency = squareBoard(5, 5, 1).adjacency;
    for (let seed = 0; seed < 50; seed++) {
      const game = new Game(adjacency, { mineCount: 24, rng: mulberry32(seed) });
      game.reveal(C(2, 3));
      expect(game.isMine(C(2, 3))).toBe(false);
      expect(game.state).not.toBe("lost");
    }
  });
  it("explicit mine positions are used", () => {
    const game = makeGame([[1, 1], [2, 2]]);
    expect(game.isMine(C(1, 1))).toBe(true);
    expect(game.isMine(C(2, 2))).toBe(true);
    expect(game.isMine(C(0, 0))).toBe(false);
  });
});

describe("adjacency", () => {
  it("counts adjacent mines", () => {
    const game = makeGame([[0, 0], [0, 1], [1, 0]]);
    expect(game.adjacentMines(C(1, 1))).toBe(3);
    expect(game.adjacentMines(C(0, 2))).toBe(1);
    expect(game.adjacentMines(C(3, 3))).toBe(0);
  });
  it("corners have three neighbors, center eight", () => {
    const game = makeGame();
    expect(game.neighbors(C(0, 0)).length).toBe(3);
    expect(game.neighbors(C(3, 3)).length).toBe(3);
    expect(game.neighbors(C(1, 1)).length).toBe(8);
  });
});

describe("reveal", () => {
  it("reveal safe cell", () => {
    const game = makeGame([[0, 0], [0, 2]]);
    game.reveal(C(0, 1));
    expect(game.cellState(C(0, 1))).toBe("revealed");
    expect(game.state).toBe("playing");
  });
  it("reveal mine loses", () => {
    const game = makeGame([[0, 0], [3, 3]]);
    game.reveal(C(1, 1));
    game.reveal(C(0, 0));
    expect(game.state).toBe("lost");
    expect(game.cellState(C(0, 0))).toBe("revealed");
  });
  it("zero cell flood fills", () => {
    const game = makeGame([[0, 0]]);
    game.reveal(C(3, 3));
    const revealed = game.cells.filter((c) => game.cellState(c) === "revealed").length;
    expect(revealed).toBe(15);
    expect(game.cellState(C(0, 0))).not.toBe("revealed");
  });
  it("flood fill stops at numbers", () => {
    const game = makeGame([[2, 0], [2, 1], [2, 2], [2, 3]]);
    game.reveal(C(0, 0));
    expect(game.cellState(C(0, 0))).toBe("revealed");
    expect(game.cellState(C(1, 1))).toBe("revealed");
    expect(game.cellState(C(3, 0))).toBe("hidden");
  });
  it("reveal flagged / unknown / post-loss are no-ops", () => {
    const g1 = makeGame();
    g1.toggleFlag(C(2, 2));
    g1.reveal(C(2, 2));
    expect(g1.cellState(C(2, 2))).toBe("flagged");

    const g2 = makeGame();
    g2.reveal(C(99, 99));
    expect(g2.state).toBe("playing");

    const g3 = makeGame([[0, 0]]);
    g3.reveal(C(0, 0));
    expect(g3.state).toBe("lost");
    g3.reveal(C(3, 3));
    expect(g3.cellState(C(3, 3))).toBe("hidden");
  });
  it("reports changed cells (revealed + auto-flagged mine on win)", () => {
    const game = makeGame([[0, 0]]);
    const changed = game.reveal(C(3, 3));
    // 15 safe cells flood open, then the win auto-flags the lone mine.
    expect(changed.length).toBe(16);
    expect(new Set(changed).size).toBe(16);
  });
});

describe("flag", () => {
  it("toggles on and off", () => {
    const game = makeGame();
    game.toggleFlag(C(1, 1));
    expect(game.cellState(C(1, 1))).toBe("flagged");
    game.toggleFlag(C(1, 1));
    expect(game.cellState(C(1, 1))).toBe("hidden");
  });
  it("cannot flag revealed cell", () => {
    const game = makeGame([[0, 0]]);
    game.reveal(C(3, 3));
    game.toggleFlag(C(3, 3));
    expect(game.cellState(C(3, 3))).toBe("revealed");
  });
  it("flags remaining counter", () => {
    const game = makeGame([[0, 0], [1, 1]]);
    expect(game.flagsRemaining).toBe(2);
    game.toggleFlag(C(0, 0));
    expect(game.flagsRemaining).toBe(1);
    game.toggleFlag(C(3, 3));
    expect(game.flagsRemaining).toBe(0);
    game.toggleFlag(C(3, 3));
    expect(game.flagsRemaining).toBe(1);
  });
});

describe("win", () => {
  it("revealing all safe cells wins", () => {
    const game = makeGame([[0, 0]]);
    game.reveal(C(3, 3));
    expect(game.state).toBe("won");
  });
  it("win on last individual reveal", () => {
    const game = makeGame([[2, 0], [2, 1], [3, 1]]);
    game.reveal(C(0, 3));
    expect(game.state).toBe("playing");
    game.reveal(C(3, 0));
    expect(game.state).toBe("won");
  });
  it("no win while safe cells remain", () => {
    const game = makeGame([[0, 0], [2, 2]]);
    game.reveal(C(0, 1));
    expect(game.state).toBe("playing");
  });
  it("win auto-flags mines and zeroes counter", () => {
    const mines = new Set([C(0, 0), C(2, 2)]);
    const game = makeGame([[0, 0], [2, 2]]);
    expect(game.flagsRemaining).toBe(2);
    for (const cell of game.cells) if (!mines.has(cell)) game.reveal(cell);
    expect(game.state).toBe("won");
    expect(game.cellState(C(0, 0))).toBe("flagged");
    expect(game.cellState(C(2, 2))).toBe("flagged");
    expect(game.flagsRemaining).toBe(0);
  });
});

describe("chord", () => {
  it("reveals unflagged neighbors", () => {
    const game = makeGame([[0, 0]]);
    game.reveal(C(1, 1));
    game.toggleFlag(C(0, 0));
    game.chord(C(1, 1));
    for (const cell of game.neighbors(C(1, 1))) {
      if (cell !== C(0, 0)) expect(game.cellState(cell)).toBe("revealed");
    }
  });
  it("without matching flags is a no-op", () => {
    const game = makeGame([[0, 0]]);
    game.reveal(C(1, 1));
    game.chord(C(1, 1));
    expect(game.cellState(C(0, 1))).toBe("hidden");
  });
  it("on hidden cell is a no-op", () => {
    const game = makeGame([[0, 0]]);
    game.chord(C(2, 2));
    expect(game.cellState(C(2, 2))).toBe("hidden");
  });
  it("with wrong flag hits a mine", () => {
    const game = makeGame([[0, 0]]);
    game.reveal(C(1, 1));
    game.toggleFlag(C(0, 1));
    game.chord(C(1, 1));
    expect(game.state).toBe("lost");
  });
});

describe("arbitrary graph", () => {
  it("works on a 4-cycle", () => {
    const adjacency = new Map<CellId, CellId[]>([
      ["0", ["1", "3"]],
      ["1", ["0", "2"]],
      ["2", ["1", "3"]],
      ["3", ["2", "0"]],
    ]);
    const game = new Game(adjacency, { minePositions: ["0"] });
    game.reveal("2");
    expect(game.state).toBe("won");
    expect(game.adjacentMines("1")).toBe(1);
  });
});
