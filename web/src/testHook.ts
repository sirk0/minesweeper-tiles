import type { CellId } from "./boards/core";

// The typed test seam Playwright drives. A canvas has no per-cell DOM, so e2e
// tests translate a cell id to current screen coordinates via `cellScreenXY`
// and read a state summary. `startBoard` accepts an explicit mine layout for
// deterministic win/lose flows. Kept small and always installed.

export interface MsState {
  screen: "menu" | "game";
  mode: string | null;
  difficulty: string | null;
  status: "playing" | "won" | "lost";
  minesRemaining: number;
  revealed: number;
  cellCount: number;
  is3d: boolean;
}

export interface MsHook {
  ready(): boolean;
  cells(): CellId[];
  cellScreenXY(cell: CellId): { x: number; y: number } | null;
  state(): MsState;
  startBoard(
    mode: string,
    difficulty: string,
    opts?: { seed?: number; mines?: CellId[] },
  ): void;
  reveal(cell: CellId): void;
  flag(cell: CellId): void;
  chord(cell: CellId): void;
  /** Rotate a 3D board as a drag of (dx, dy) CSS pixels would; no-op on
   * flat boards. */
  rotate(dxPx: number, dyPx: number): void;
  /** Walk the Klein cell cycle one step (+1 forward, -1 back); no-op on boards
   * without one. */
  scroll(direction: number): void;
}

declare global {
  interface Window {
    __ms?: MsHook;
  }
}

export function installTestHook(hook: MsHook): void {
  window.__ms = hook;
}
