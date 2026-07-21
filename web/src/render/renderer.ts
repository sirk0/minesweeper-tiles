import {
  Color,
  DirectionalLight,
  HemisphereLight,
  OrthographicCamera,
  Raycaster,
  Scene,
  Vector2,
  WebGLRenderer,
} from "three";
import type { BoardMesh } from "./boardMesh";

// One rendering pipeline. M0 uses only the orthographic (flat-board) path; the
// perspective/trackball path for 3D surfaces arrives in M2. Resize is
// DPR-aware and clamped to 2 to bound cost on retina displays.

export class BoardRenderer {
  readonly renderer: WebGLRenderer;
  readonly scene: Scene;
  readonly camera: OrthographicCamera;
  private readonly raycaster = new Raycaster();
  private board: BoardMesh | null = null;
  private frameHandle = 0;
  private dirty = true;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    this.renderer.setClearColor(new Color("#1b1f24"), 1);

    this.scene = new Scene();
    this.camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
    this.camera.position.set(0, 0, 10);
    this.camera.lookAt(0, 0, 0);

    const hemi = new HemisphereLight(0xffffff, 0x404650, 0.85);
    this.scene.add(hemi);
    const key = new DirectionalLight(0xffffff, 1.1);
    key.position.set(-3, 5, 8);
    this.scene.add(key);
  }

  setBoard(board: BoardMesh): void {
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
      // Fit the board (spanning cols x rows around the origin) with a margin.
      const margin = 1.1;
      const halfW = (this.board.cols * margin) / 2;
      const halfH = (this.board.rows * margin) / 2;
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

  /** Cell under normalized device coords (-1..1), or -1. */
  pick(ndc: Vector2): number {
    if (!this.board) return -1;
    this.raycaster.setFromCamera(ndc, this.camera);
    const cells = this.board.getObjectByName("cells");
    if (!cells) return -1;
    const hits = this.raycaster.intersectObject(cells, false);
    const hit = hits[0];
    if (!hit || hit.faceIndex == null) return -1;
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
