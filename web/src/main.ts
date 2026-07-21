import { Vector2, Vector3 } from "three";
import "./ui/styles.css";
import { BoardRenderer } from "./render/renderer";
import { BoardMesh } from "./render/boardMesh";
import { makeDemoBoard } from "./render/demoBoard";
import { Hud } from "./ui/hud";
import { Menu } from "./ui/menu";
import { installTestHook } from "./testHook";

// M0 bootstrap: mount the render-pipeline-proof board, the config-driven HUD,
// and the menu shell, wire hover picking, and expose the Playwright test seam.
class App {
  private readonly renderer: BoardRenderer;
  private board: BoardMesh;
  private readonly hud: Hud;
  private readonly menu: Menu;
  private hovered = -1;
  private screen: "game" | "menu" = "game";

  constructor(canvas: HTMLCanvasElement, ui: HTMLElement) {
    this.renderer = new BoardRenderer(canvas);
    this.board = makeDemoBoard();
    this.renderer.setBoard(this.board);

    this.hud = new Hud((action) => this.onAction(action));
    this.menu = new Menu(() => this.showGame());
    ui.append(this.hud.root, this.menu.root);
    this.hud.setState({ minesRemaining: 10, elapsedSeconds: 0, status: "playing" });

    window.addEventListener("resize", () => this.renderer.resize());
    canvas.addEventListener("pointermove", (e) => this.onPointerMove(e));
    canvas.addEventListener("pointerleave", () => this.setHover(-1));

    this.renderer.start();
    installTestHook({
      ready: () => true,
      cellCount: () => this.board.cellCount,
      cellScreenXY: (cell) => this.cellScreenXY(cell),
      state: () => ({
        screen: this.screen,
        cells: this.board.cellCount,
        hovered: this.hovered,
      }),
      setHover: (cell) => this.setHover(cell),
    });
    requestAnimationFrame(() => document.body.setAttribute("data-ready", "1"));
  }

  private onAction(action: string): void {
    if (action === "menu") this.showMenu();
    else if (action === "restart") this.hud.setState({ elapsedSeconds: 0, status: "playing" });
  }

  private showMenu(): void {
    this.screen = "menu";
    this.menu.show();
  }
  private showGame(): void {
    this.screen = "game";
    this.menu.hide();
    this.renderer.resize();
  }

  private ndcFromEvent(e: PointerEvent, canvas: HTMLElement): Vector2 {
    const r = canvas.getBoundingClientRect();
    return new Vector2(
      ((e.clientX - r.left) / r.width) * 2 - 1,
      -(((e.clientY - r.top) / r.height) * 2 - 1),
    );
  }

  private onPointerMove(e: PointerEvent): void {
    if (this.screen !== "game") return;
    const cell = this.renderer.pick(this.ndcFromEvent(e, e.currentTarget as HTMLElement));
    this.setHover(cell);
  }

  private setHover(cell: number): void {
    if (cell === this.hovered) return;
    this.hovered = cell;
    this.board.setHover(cell);
    this.renderer.markDirty();
  }

  private cellScreenXY(cell: number): { x: number; y: number } | null {
    if (cell < 0 || cell >= this.board.cellCount) return null;
    const [lx, ly] = this.board.cellCenter(cell);
    const world = new Vector3(lx, ly, 0).add(this.board.position);
    const ndc = world.project(this.renderer.camera);
    const canvas = this.renderer.renderer.domElement;
    const r = canvas.getBoundingClientRect();
    return {
      x: r.left + ((ndc.x + 1) / 2) * r.width,
      y: r.top + ((1 - ndc.y) / 2) * r.height,
    };
  }
}

const canvas = document.getElementById("board") as HTMLCanvasElement;
const ui = document.getElementById("ui") as HTMLElement;
new App(canvas, ui);
