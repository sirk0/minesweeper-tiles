// Port of minesweeper/game.py — core minesweeper rules over an arbitrary cell
// graph (adjacency map). Knows nothing about geometry or rendering.
import type { CellId } from "./boards/core";
import { mulberry32, sample, type Rng } from "./rng";

export type CellState = "hidden" | "revealed" | "flagged";
export type GameState = "playing" | "won" | "lost";

export interface GameOptions {
  mineCount?: number;
  minePositions?: Iterable<CellId>;
  rng?: Rng;
}

export class Game {
  readonly mineCount: number;
  state: GameState = "playing";

  private readonly adjacency: Map<CellId, CellId[]>;
  private readonly rng: Rng;
  private mines: Set<CellId>;
  private minesPlaced: boolean;
  private readonly cellStates = new Map<CellId, CellState>();
  private revealedCount = 0;

  constructor(
    adjacency: Map<CellId, Iterable<CellId>>,
    options: GameOptions = {},
  ) {
    this.adjacency = new Map();
    for (const [cell, neighbors] of adjacency) {
      this.adjacency.set(cell, [...neighbors]);
    }
    if (this.adjacency.size === 0) throw new Error("board has no cells");
    for (const [cell, neighbors] of this.adjacency) {
      for (const n of neighbors) {
        if (!this.adjacency.has(n)) {
          throw new Error(`neighbor ${n} of ${cell} is not a board cell`);
        }
      }
    }

    let mineCount = options.mineCount;
    const explicit = options.minePositions
      ? new Set(options.minePositions)
      : null;
    if (explicit) {
      for (const m of explicit) {
        if (!this.adjacency.has(m)) {
          throw new Error(`mine position not on the board: ${m}`);
        }
      }
      mineCount = explicit.size;
    }
    if (mineCount == null || mineCount < 1) {
      throw new Error("need at least one mine");
    }
    if (mineCount >= this.adjacency.size) {
      throw new Error("mine count must leave at least one safe cell");
    }

    this.mineCount = mineCount;
    this.rng = options.rng ?? mulberry32((Math.random() * 2 ** 32) >>> 0);
    this.mines = explicit ?? new Set();
    this.minesPlaced = explicit != null;
    for (const cell of this.adjacency.keys()) this.cellStates.set(cell, "hidden");
  }

  // -- queries ---------------------------------------------------------------

  get cells(): CellId[] {
    return [...this.adjacency.keys()];
  }

  neighbors(cell: CellId): CellId[] {
    return this.adjacency.get(cell) ?? [];
  }

  cellState(cell: CellId): CellState {
    return this.cellStates.get(cell)!;
  }

  isMine(cell: CellId): boolean {
    return this.mines.has(cell);
  }

  adjacentMines(cell: CellId): number {
    let n = 0;
    for (const neighbor of this.adjacency.get(cell) ?? []) {
      if (this.mines.has(neighbor)) n++;
    }
    return n;
  }

  get flagsRemaining(): number {
    let flagged = 0;
    for (const s of this.cellStates.values()) if (s === "flagged") flagged++;
    return this.mineCount - flagged;
  }

  get revealed(): number {
    return this.revealedCount;
  }

  // -- moves -----------------------------------------------------------------

  /** Reveal a cell; changed cells are returned for ranged rendering updates. */
  reveal(cell: CellId): CellId[] {
    if (this.state !== "playing" || !this.adjacency.has(cell)) return [];
    if (this.cellStates.get(cell) !== "hidden") return [];

    if (!this.minesPlaced) this.placeMines(cell);

    if (this.mines.has(cell)) {
      this.cellStates.set(cell, "revealed");
      this.state = "lost";
      return [cell];
    }

    const changed = this.floodReveal(cell);
    if (this.revealedCount === this.adjacency.size - this.mineCount) {
      this.state = "won";
      for (const mine of this.mines) {
        if (this.cellStates.get(mine) === "hidden") {
          this.cellStates.set(mine, "flagged");
          changed.push(mine);
        }
      }
    }
    return changed;
  }

  toggleFlag(cell: CellId): CellId[] {
    if (this.state !== "playing" || !this.adjacency.has(cell)) return [];
    const current = this.cellStates.get(cell);
    if (current === "hidden") {
      this.cellStates.set(cell, "flagged");
      return [cell];
    }
    if (current === "flagged") {
      this.cellStates.set(cell, "hidden");
      return [cell];
    }
    return [];
  }

  /** Reveal all unflagged neighbours of a revealed cell whose flag count
   * matches its adjacent-mine count. */
  chord(cell: CellId): CellId[] {
    if (this.state !== "playing" || !this.adjacency.has(cell)) return [];
    if (this.cellStates.get(cell) !== "revealed") return [];
    const neighbors = this.adjacency.get(cell)!;
    let flagged = 0;
    for (const n of neighbors) if (this.cellStates.get(n) === "flagged") flagged++;
    if (flagged !== this.adjacentMines(cell)) return [];
    const changed: CellId[] = [];
    for (const n of neighbors) {
      if (this.cellStates.get(n) === "hidden") {
        changed.push(...this.reveal(n));
        if (this.state !== "playing") return changed;
      }
    }
    return changed;
  }

  // -- internals -------------------------------------------------------------

  private placeMines(safe: CellId): void {
    const candidates = this.cells.filter((c) => c !== safe);
    this.mines = new Set(sample(candidates, this.mineCount, this.rng));
    this.minesPlaced = true;
  }

  private floodReveal(cell: CellId): CellId[] {
    const changed: CellId[] = [];
    const stack = [cell];
    while (stack.length) {
      const current = stack.pop()!;
      if (this.cellStates.get(current) !== "hidden") continue;
      this.cellStates.set(current, "revealed");
      this.revealedCount++;
      changed.push(current);
      if (this.adjacentMines(current) === 0) {
        stack.push(...(this.adjacency.get(current) ?? []));
      }
    }
    return changed;
  }
}
