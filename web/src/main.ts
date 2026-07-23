import { Vector3 } from "three";
import "./ui/styles.css";
import { isBoard3D, type CellId } from "./boards/core";
import { hasMode } from "./boards/presets";
import { DIFFICULTIES } from "./boards/catalog";
import { screens } from "./config/screens";
import { GameSession } from "./session";
import { attachControls } from "./input/controls";
import {
  BoardRenderer,
  initialOrientation,
  KEY_ROTATE_STEP,
} from "./render/renderer";
import { Hud } from "./ui/hud";
import { Menu } from "./ui/menu";
import { installTestHook } from "./testHook";

// App bootstrap: menu launches a ported board; deep links start one directly;
// input drives reveal/flag/chord (and, on 3D boards, drag/arrow-key rotation)
// through the GameSession; the HUD and menu render from the shared UI-screen
// config; the test seam is exposed.
class App {
  private readonly renderer: BoardRenderer;
  private readonly hud: Hud;
  private readonly menu: Menu;
  private session: GameSession | null = null;
  private screen: "menu" | "game" = "menu";
  private flagMode = false;
  private hovered: CellId | null = null;
  // Board animations honour the OS reduced-motion setting out of the gate; the
  // `window.__ms.animations(false)` test seam overrides it for deterministic e2e.
  private animationsEnabled = !(
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false
  );

  constructor(
    private readonly canvas: HTMLCanvasElement,
    ui: HTMLElement,
  ) {
    this.renderer = new BoardRenderer(canvas);
    this.hud = new Hud((action) => this.onAction(action));
    this.menu = new Menu((sel) => this.startGame(sel.mode, sel.difficulty));
    ui.append(this.hud.root, this.menu.root);
    this.hud.root.hidden = true;

    window.addEventListener("resize", () => this.renderer.resize());
    window.addEventListener("keydown", (e) => this.onKey(e));
    attachControls(canvas, {
      pick: (ndc) => this.renderer.pick(ndc),
      onTap: (cell) => this.onTap(cell),
      onLongPress: (cell) => this.flag(cell),
      onSecondary: (cell) => this.flag(cell),
      onHover: (cell) => this.hover(cell),
      rotates: () => this.screen === "game" && (this.session?.is3d ?? false),
      onRotate: (dx, dy) => this.rotate(dx, dy),
      onScroll: (direction) => this.scroll(direction),
    });
    this.renderer.start();
    window.setInterval(() => this.tickTimer(), 250);

    this.installSeam();
    if (!this.startFromDeepLink()) this.showMenu();
    requestAnimationFrame(() => document.body.setAttribute("data-ready", "1"));
  }

  // -- navigation ------------------------------------------------------------

  private startFromDeepLink(): boolean {
    const params = new URLSearchParams(window.location.search);
    const mode = params.get("mode");
    const difficulty = params.get("difficulty") ?? screens.defaultDifficulty;
    const seedRaw = params.get("seed");
    if (!mode || !hasMode(mode) || !DIFFICULTIES.includes(difficulty)) return false;
    const seed = seedRaw != null ? Number(seedRaw) : undefined;
    this.startGame(mode, difficulty, seed !== undefined && !Number.isNaN(seed) ? { seed } : {});
    return true;
  }

  private startGame(
    mode: string,
    difficulty: string,
    opts: { seed?: number; mines?: CellId[] } = {},
  ): void {
    this.session = new GameSession(mode, difficulty, {
      ...(opts.seed !== undefined ? { seed: opts.seed } : {}),
      ...(opts.mines ? { minePositions: opts.mines } : {}),
    });
    this.renderer.setBoard(this.session.mesh);
    this.session.mesh.setAnimationsEnabled(this.animationsEnabled);
    if (this.session.is3d) this.renderer.setOrientation(initialOrientation(mode));
    this.screen = "game";
    this.menu.hide();
    this.hud.root.hidden = false;
    this.hovered = null;
    this.flagMode = false;
    this.syncHud();
    this.renderer.resize();
  }

  private showMenu(): void {
    this.screen = "menu";
    this.hud.root.hidden = true;
    this.menu.show();
  }

  private onAction(action: string): void {
    if (action === "menu") this.showMenu();
    else if (action === "toggle-flag-mode") {
      this.flagMode = !this.flagMode;
      this.hud.setState({ flagMode: this.flagMode });
    } else if (action === "restart" && this.session) {
      this.startGame(this.session.mode, this.session.difficulty);
    } else if (action === "klein-scroll-back") {
      this.scroll(-1);
    } else if (action === "klein-scroll-fwd") {
      this.scroll(1);
    }
  }

  // -- gameplay --------------------------------------------------------------

  private onTap(cell: CellId): void {
    if (!this.session || this.screen !== "game") return;
    if (this.flagMode) {
      this.session.flag(cell);
    } else if (this.session.game.cellState(cell) === "revealed") {
      this.session.chord(cell);
    } else {
      this.session.reveal(cell);
    }
    this.afterMove();
  }

  private flag(cell: CellId): void {
    if (!this.session || this.screen !== "game") return;
    this.session.flag(cell);
    this.afterMove();
  }

  private hover(cell: CellId | null): void {
    if (!this.session || this.screen !== "game") return;
    if (cell === this.hovered) return;
    this.hovered = cell;
    this.session.hover(cell);
    this.renderer.markDirty();
  }

  private rotate(dxPx: number, dyPx: number): void {
    if (!this.session?.is3d || this.screen !== "game") return;
    this.renderer.rotateBy(dxPx, dyPx);
  }

  /** Walk the Klein cell cycle one step (view-layer permutation); no-op on
   * boards without one. */
  private scroll(direction: number): void {
    if (this.screen !== "game") return;
    if (this.session?.scroll(direction)) {
      this.renderer.markDirty();
    }
  }

  private onKey(e: KeyboardEvent): void {
    if (this.screen !== "game" || !this.session?.is3d) return;
    // Bracket keys walk the Klein cell cycle (matching the wheel / scroll
    // arrows); arrows rotate the board.
    if (e.key === "[") this.scroll(-1);
    else if (e.key === "]") this.scroll(1);
    else {
      const step = KEY_ROTATE_STEP;
      if (e.key === "ArrowLeft") this.rotate(-step, 0);
      else if (e.key === "ArrowRight") this.rotate(step, 0);
      else if (e.key === "ArrowUp") this.rotate(0, -step);
      else if (e.key === "ArrowDown") this.rotate(0, step);
      else return;
    }
    e.preventDefault();
  }

  private afterMove(): void {
    this.syncHud();
    this.renderer.markDirty();
  }

  private tickTimer(): void {
    if (this.session && this.session.status === "playing") this.syncHud();
  }

  private syncHud(): void {
    if (!this.session) return;
    const s = this.session.hud();
    this.hud.setState({
      minesRemaining: s.minesRemaining,
      elapsedSeconds: s.elapsedSeconds,
      status: s.status,
      flagMode: this.flagMode,
      hasCellCycle: this.session.hasCellCycle,
    });
  }

  // -- test seam -------------------------------------------------------------

  /** Screen coords of a cell's centre, or null when the cell currently faces
   * away from the camera (3D boards) — tests pick a visible cell instead. */
  private cellScreenXY(cell: CellId): { x: number; y: number } | null {
    if (!this.session) return null;
    const mesh = this.session.mesh;
    // A game cell's contents are painted on its (possibly scrolled) geometric
    // face; anchor there so the reported position follows the Klein scroll.
    const anchor = mesh.cellAnchor(this.session.geomFor(cell));
    if (!anchor) return null;
    mesh.updateWorldMatrix(true, false);
    const world = new Vector3(...anchor.center).applyMatrix4(mesh.matrixWorld);
    const camera = this.renderer.camera;
    const board = this.session.board;
    // A closed solid hides a cell that faces away; a two-sided surface shows
    // its cells from both faces, so it is never culled here.
    if (this.session.is3d && !(isBoard3D(board) && board.twoSided)) {
      const normal = new Vector3(...anchor.normal).transformDirection(mesh.matrixWorld);
      const toCamera = camera.position.clone().sub(world);
      if (normal.dot(toCamera) <= 1e-6) return null; // back-facing
    }
    const ndc = world.project(camera);
    const r = this.canvas.getBoundingClientRect();
    return {
      x: r.left + ((ndc.x + 1) / 2) * r.width,
      y: r.top + ((1 - ndc.y) / 2) * r.height,
    };
  }

  private installSeam(): void {
    installTestHook({
      ready: () => true,
      cells: () => (this.session ? this.session.game.cells : []),
      cellScreenXY: (cell) => this.cellScreenXY(cell),
      startBoard: (mode, difficulty, opts) => {
        this.startGame(mode, difficulty, opts ?? {});
      },
      reveal: (cell) => {
        this.session?.reveal(cell);
        this.afterMove();
      },
      flag: (cell) => this.flag(cell),
      chord: (cell) => {
        this.session?.chord(cell);
        this.afterMove();
      },
      rotate: (dxPx, dyPx) => this.rotate(dxPx, dyPx),
      scroll: (direction) => this.scroll(direction),
      animations: (enabled) => {
        this.animationsEnabled = enabled;
        this.session?.mesh.setAnimationsEnabled(enabled);
      },
      state: () => {
        const s = this.session;
        return {
          screen: this.screen,
          mode: s?.mode ?? null,
          difficulty: s?.difficulty ?? null,
          status: s?.status ?? "playing",
          minesRemaining: s ? s.hud().minesRemaining : 0,
          revealed: s ? s.game.revealed : 0,
          cellCount: s ? s.game.cells.length : 0,
          is3d: s?.is3d ?? false,
        };
      },
    });
  }
}

const canvas = document.getElementById("board") as HTMLCanvasElement;
const ui = document.getElementById("ui") as HTMLElement;
new App(canvas, ui);
