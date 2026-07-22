import {
  Color,
  DirectionalLight,
  Group,
  HemisphereLight,
  OrthographicCamera,
  Raycaster,
  Scene,
  Vector2,
  WebGLRenderer,
} from "three";
import type { CellId } from "../boards/core";

// One rendering pipeline. M1 uses the orthographic (flat-board) path; the
// perspective/trackball path for 3D surfaces arrives in M2. Resize is
// DPR-aware and clamped to 2 to bound cost on retina displays.

export interface RenderBoard extends Group {
  readonly extent: { width: number; height: number };
  cellForFace(faceIndex: number): CellId | null;
}

export class BoardRenderer {
  readonly renderer: WebGLRenderer;
  readonly scene: Scene;
  readonly camera: OrthographicCamera;
  private readonly raycaster = new Raycaster();
  private board: RenderBoard | null = null;
  private frameHandle = 0;
  private dirty = true;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    // Classic minesweeper silver-gray field (no dark background).
    this.renderer.setClearColor(new Color("#c0c0c0"), 1);

    this.scene = new Scene();
    // The board lives in pixel units (hundreds wide) with per-cell bevel
    // heights that scale with cell size, so place the camera far back in z and
    // give it a deep frustum: otherwise big cells (e.g. triangle boards) poke
    // past a nearby near plane and become invisible to the picking ray.
    this.camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 4000);
    this.camera.position.set(0, 0, 2000);
    this.camera.lookAt(0, 0, 0);

    // Soft ambient plus a directional key from the top-left so the tile bevels
    // catch a highlight/shadow (the classic raised-button look) without
    // blowing the light-gray faces out to white.
    const hemi = new HemisphereLight(0xffffff, 0x9a9a9a, 0.9);
    this.scene.add(hemi);
    const key = new DirectionalLight(0xffffff, 0.55);
    key.position.set(-4, 6, 8);
    this.scene.add(key);
  }

  setBoard(board: RenderBoard): void {
    if (this.board) this.scene.remove(this.board);
    this.board = board;
    this.scene.add(board);
    this.resize();
    this.dirty = true;
  }

  markDirty(): void {
    this.dirty = true;
  }

  resize(): void {
    const w = this.canvas.clientWidth || window.innerWidth;
    const h = this.canvas.clientHeight || window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(w, h, false);

    if (this.board) {
      const margin = 1.06;
      const halfW = (this.board.extent.width * margin) / 2;
      const halfH = (this.board.extent.height * margin) / 2;
      const aspect = w / h;
      let x = halfW;
      let y = halfH;
      if (halfW / halfH > aspect) y = halfW / aspect;
      else x = halfH * aspect;
      this.camera.left = -x;
      this.camera.right = x;
      this.camera.top = y;
      this.camera.bottom = -y;
      this.camera.updateProjectionMatrix();
    }
    this.dirty = true;
  }

  /** Cell under normalized device coords (-1..1), or null. */
  pick(ndc: Vector2): CellId | null {
    if (!this.board) return null;
    this.raycaster.setFromCamera(ndc, this.camera);
    const cells = this.board.getObjectByName("cells");
    if (!cells) return null;
    const hits = this.raycaster.intersectObject(cells, false);
    const hit = hits[0];
    if (!hit || hit.faceIndex == null) return null;
    return this.board.cellForFace(hit.faceIndex);
  }

  private renderOnce = (): void => {
    if (this.dirty) {
      this.renderer.render(this.scene, this.camera);
      this.dirty = false;
    }
    this.frameHandle = requestAnimationFrame(this.renderOnce);
  };

  start(): void {
    if (!this.frameHandle) this.renderOnce();
  }

  stop(): void {
    if (this.frameHandle) cancelAnimationFrame(this.frameHandle);
    this.frameHandle = 0;
  }
}
