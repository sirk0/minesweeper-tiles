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

  // View-layer scroll for the Klein bottle. `cycle` is the one-step ring
  // translation (a graph automorphism); scrolling walks a permutation between
  // geometric faces and the game cells painted on them, so cells hidden behind
  // the self-intersection rotate into view without the geometry moving.
  // `remap` sends each geometric face -> the game cell shown on it (identity
  // until scrolled); `remapInv` is its inverse (game cell -> geometric face).
  private readonly cycle: Map<CellId, CellId> | null;
  private readonly cycleInv: Map<CellId, CellId> | null;
  private remap = new Map<CellId, CellId>();
  private remapInv = new Map<CellId, CellId>();

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
    this.cycle = isBoard3D(this.board) ? this.board.cellCycle : null;
    this.cycleInv = this.cycle ? invert(this.cycle) : null;
    for (const cell of this.board.polygons.keys()) {
      this.remap.set(cell, cell);
      this.remapInv.set(cell, cell);
    }
  }

  get status() {
    return this.game.state;
  }

  get is3d(): boolean {
    return isBoard3D(this.board);
  }

  /** Whether this board carries a ring translation the player can scroll along
   * (the Klein bottle). Drives the HUD scroll arrows and wheel/gesture input. */
  get hasCellCycle(): boolean {
    return this.cycle != null;
  }

  /** The geometric face a game cell's contents are currently painted on
   * (identity until the board is scrolled). The test seam maps a cell's screen
   * position through this. */
  geomFor(gameCell: CellId): CellId {
    return this.remapInv.get(gameCell) ?? gameCell;
  }

  private toGame(geomCell: CellId): CellId {
    return this.remap.get(geomCell) ?? geomCell;
  }

  /** Scroll the cell contents one step along the ring: `direction` > 0 forward
   * (`cycle`), < 0 backward (`cycleInv`). No-op off a Klein board. Returns
   * whether it scrolled. */
  scroll(direction: number): boolean {
    if (!this.cycle || !this.cycleInv) return false;
    const cyc = direction > 0 ? this.cycle : this.cycleInv;
    const next = new Map<CellId, CellId>();
    for (const [geom, game] of this.remap) next.set(geom, cyc.get(game) ?? game);
    this.remap = next;
    this.remapInv = invert(next);
    for (const geom of this.board.polygons.keys()) {
      this.mesh.setVisual(geom, this.visualFor(this.toGame(geom)));
    }
    return true;
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
    const gameCell = this.toGame(cell);
    const changed = this.game.reveal(gameCell);
    if (this.game.state === "lost") this.exploded = gameCell;
    this.apply(changed);
    this.checkStop();
  }

  flag(cell: CellId): void {
    this.startTimer();
    this.apply(this.game.toggleFlag(this.toGame(cell)));
  }

  chord(cell: CellId): void {
    if (this.status !== "playing") return;
    this.startTimer();
    const changed = this.game.chord(this.toGame(cell));
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
    for (const cell of changed) {
      this.mesh.setVisual(this.geomFor(cell), this.visualFor(cell));
    }
  }

  private revealAllMines(): void {
    for (const cell of this.game.cells) {
      if (this.game.isMine(cell) && this.game.cellState(cell) !== "flagged") {
        this.mesh.setVisual(this.geomFor(cell), this.visualFor(cell));
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

function invert(map: Map<CellId, CellId>): Map<CellId, CellId> {
  const out = new Map<CellId, CellId>();
  for (const [k, v] of map) out.set(v, k);
  return out;
}
