// Tiny, typed test seam bridging the canvas game to Playwright. A canvas has
// no per-cell DOM, so e2e tests translate a cell id to current screen
// coordinates through `cellScreenXY` and read a state summary. Kept minimal and
// always installed (harmless in production); richer hooks (setMines, rotation)
// arrive with the game logic in M1+.

export interface MsHook {
  ready(): boolean;
  cellCount(): number;
  cellScreenXY(cell: number): { x: number; y: number } | null;
  state(): { screen: string; cells: number; hovered: number };
  setHover(cell: number): void;
}

declare global {
  interface Window {
    __ms?: MsHook;
  }
}

export function installTestHook(hook: MsHook): void {
  window.__ms = hook;
}
