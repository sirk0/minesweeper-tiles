import { buildBoard } from "./boards/presets";
import { isBoard3D, type AnyBoard, type CellId } from "./boards/core";
import { Game } from "./game";
import { mulberry32, type Rng } from "./rng";
import type { BoardMesh, CellVisual } from "./render/boardMesh";
import { PolygonBoard } from "./render/polygonBoard";
import { SolidBoard } from "./render/solidBoard";

// GameSession mediates between the pure Game (rules), the board mesh (flat
// PolygonBoard or 3D SolidBoard), and the HUD. Each move syncs only the
// changed cells into the mesh and reports HUD state.

export interface HudSnapshot {
  minesRemaining: number;
  elapsedSeconds: number;
  status: "playing" | "won" | "lost";
}

export class GameSession {
  readonly board: AnyBoard;
  readonly mesh: BoardMesh;
  readonly game: Game;
  readonly mode: string;
  readonly difficulty: string;

  private exploded: CellId | null = null;
  private startedAt: number | null = null;
  private stoppedAt: number | null = null;

  constructor(
    mode: string,
    difficulty: string,
    opts: { seed?: number; minePositions?: CellId[] } = {},
  ) {
    this.mode = mode;
    this.difficulty = difficulty;
    this.board = buildBoard(mode, difficulty);
    this.mesh = isBoard3D(this.board)
      ? new SolidBoard(this.board)
      : new PolygonBoard(this.board);
    const rng: Rng | undefined =
      opts.seed !== undefined ? mulberry32(opts.seed >>> 0) : undefined;
    this.game = new Game(this.board.adjacency, {
      mineCount: this.board.mineCount,
      ...(opts.minePositions ? { minePositions: opts.minePositions } : {}),
      ...(rng ? { rng } : {}),
    });
  }

  get status() {
    return this.game.state;
  }

  get is3d(): boolean {
    return isBoard3D(this.board);
  }

  hud(): HudSnapshot {
    return {
      minesRemaining: this.game.flagsRemaining,
      elapsedSeconds: this.elapsed(),
      status: this.game.state,
    };
  }

  private elapsed(): number {
    if (this.startedAt == null) return 0;
    const end = this.stoppedAt ?? performance.now();
    return Math.floor((end - this.startedAt) / 1000);
  }

  reveal(cell: CellId): void {
    if (this.status !== "playing") return;
    this.startTimer();
    const changed = this.game.reveal(cell);
    if (this.game.state === "lost") this.exploded = cell;
    this.apply(changed);
    this.checkStop();
  }

  flag(cell: CellId): void {
    this.startTimer();
    this.apply(this.game.toggleFlag(cell));
  }

  chord(cell: CellId): void {
    if (this.status !== "playing") return;
    this.startTimer();
    const changed = this.game.chord(cell);
    if (this.game.state === "lost") {
      // the mine that ended the chord is whichever revealed mine exists
      for (const c of changed) if (this.game.isMine(c)) this.exploded = c;
    }
    this.apply(changed);
    this.checkStop();
  }

  hover(cell: CellId | null): void {
    this.mesh.setHover(cell);
  }

  private startTimer(): void {
    if (this.startedAt == null) this.startedAt = performance.now();
  }

  private checkStop(): void {
    if (this.game.state !== "playing" && this.stoppedAt == null) {
      this.stoppedAt = performance.now();
      if (this.game.state === "lost") this.revealAllMines();
    }
  }

  private apply(changed: CellId[]): void {
    for (const cell of changed) this.mesh.setVisual(cell, this.visualFor(cell));
  }

  private revealAllMines(): void {
    for (const cell of this.game.cells) {
      if (this.game.isMine(cell) && this.game.cellState(cell) !== "flagged") {
        this.mesh.setVisual(cell, this.visualFor(cell));
      }
    }
  }

  private visualFor(cell: CellId): CellVisual {
    const state = this.game.cellState(cell);
    if (state === "flagged") return { kind: "flagged" };
    if (state === "revealed") {
      if (this.game.isMine(cell)) {
        return cell === this.exploded ? { kind: "exploded" } : { kind: "mine" };
      }
      return { kind: "revealed", mines: this.game.adjacentMines(cell) };
    }
    if (this.game.state === "lost" && this.game.isMine(cell)) {
      return { kind: "mine" };
    }
    return { kind: "hidden" };
  }
}
