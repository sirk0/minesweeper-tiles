import {
  Color,
  DirectionalLight,
  HemisphereLight,
  OrthographicCamera,
  PerspectiveCamera,
  Quaternion,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import type { CellId } from "../boards/core";
import { surfaceOf, viewHint } from "../boards/catalog";
import type { BoardMesh } from "./boardMesh";

// One rendering pipeline for both board families. Flat boards use the
// orthographic camera fit to the board extent; solids are scaled to the unit
// sphere and viewed by the perspective camera, rotated by a small custom
// trackball (drag deltas premultiply the board's quaternion, matching the
// pygame renderer's `rotation = turn * rotation`). Resize is DPR-aware and
// clamped to 2 to bound cost on retina displays.

/** Radians of board rotation per CSS pixel of drag — the pygame feel. */
export const ROTATE_SPEED = 0.008;
/** Drag-pixels-worth of rotation per arrow-key press (0.32 rad). */
export const KEY_ROTATE_STEP = 40;

const SOLID_FOV = 40; // degrees
const SOLID_MARGIN = 1.12; // frame the unit sphere with a little air

const X_AXIS = new Vector3(1, 0, 0);
const Y_AXIS = new Vector3(0, 1, 0);

export class BoardRenderer {
  readonly renderer: WebGLRenderer;
  readonly scene: Scene;
  readonly orthoCamera: OrthographicCamera;
  readonly perspCamera: PerspectiveCamera;
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
    // Classic minesweeper silver-gray field (no dark background).
    this.renderer.setClearColor(new Color("#c0c0c0"), 1);

    this.scene = new Scene();
    // The flat board lives in pixel units (hundreds wide) with per-cell bevel
    // heights that scale with cell size, so place the camera far back in z and
    // give it a deep frustum: otherwise big cells (e.g. triangle boards) poke
    // past a nearby near plane and become invisible to the picking ray.
    this.orthoCamera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 4000);
    this.orthoCamera.position.set(0, 0, 2000);
    this.orthoCamera.lookAt(0, 0, 0);

    this.perspCamera = new PerspectiveCamera(SOLID_FOV, 1, 0.1, 20);
    this.perspCamera.position.set(0, 0, 4);
    this.perspCamera.lookAt(0, 0, 0);

    // Soft ambient plus a directional key from the top-left so the tile bevels
    // catch a highlight/shadow (the classic raised-button look) without
    // blowing the light-gray faces out to white. The lights are fixed in world
    // space, so rotating a solid sweeps its faces through the light.
    const hemi = new HemisphereLight(0xffffff, 0x9a9a9a, 0.9);
    this.scene.add(hemi);
    const key = new DirectionalLight(0xffffff, 0.55);
    key.position.set(-4, 6, 8);
    this.scene.add(key);
  }

  /** The camera matching the current board's view kind. */
  get camera(): OrthographicCamera | PerspectiveCamera {
    return this.board?.view.kind === "solid"
      ? this.perspCamera
      : this.orthoCamera;
  }

  setBoard(board: BoardMesh): void {
    if (this.board) this.scene.remove(this.board);
    this.board = board;
    if (board.view.kind === "solid") {
      // Scale the solid into the unit sphere so one camera setup frames all.
      board.scale.setScalar(1 / board.view.radius);
    }
    this.scene.add(board);
    this.resize(); // frames the camera, then re-orients the board (below)
    this.dirty = true;
  }

  /** Replace the board's orientation (used for per-mode initial views). */
  setOrientation(q: Quaternion): void {
    if (!this.board) return;
    this.board.quaternion.copy(q);
    this.board.orient?.(this.board.quaternion, this.perspCamera.position);
    this.dirty = true;
  }

  /** Trackball: rotate the board by a drag of (dx, dy) CSS pixels — yaw
   * around the world y-axis, pitch around the world x-axis, premultiplied so
   * the board turns under the cursor regardless of its current orientation.
   * Dragging down tilts the top toward the viewer. */
  rotateBy(dxPx: number, dyPx: number): void {
    if (!this.board || this.board.view.kind !== "solid") return;
    const turn = new Quaternion()
      .setFromAxisAngle(X_AXIS, dyPx * ROTATE_SPEED)
      .multiply(
        new Quaternion().setFromAxisAngle(Y_AXIS, dxPx * ROTATE_SPEED),
      );
    this.board.quaternion.premultiply(turn);
    this.board.orient?.(this.board.quaternion, this.perspCamera.position);
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

    const view = this.board?.view;
    if (view?.kind === "flat") {
      const margin = 1.06;
      const halfW = (view.width * margin) / 2;
      const halfH = (view.height * margin) / 2;
      const aspect = w / h;
      let x = halfW;
      let y = halfH;
      if (halfW / halfH > aspect) y = halfW / aspect;
      else x = halfH * aspect;
      this.orthoCamera.left = -x;
      this.orthoCamera.right = x;
      this.orthoCamera.top = y;
      this.orthoCamera.bottom = -y;
      this.orthoCamera.updateProjectionMatrix();
    } else if (view?.kind === "solid") {
      const aspect = w / h;
      this.perspCamera.aspect = aspect;
      // Back the camera off until the unit sphere fits the narrower fov axis.
      const halfY = (SOLID_FOV * Math.PI) / 360;
      const halfX = Math.atan(Math.tan(halfY) * aspect);
      const dist = SOLID_MARGIN / Math.sin(Math.min(halfX, halfY));
      this.perspCamera.position.set(0, 0, dist);
      this.perspCamera.near = Math.max(0.05, dist - 2);
      this.perspCamera.far = dist + 2;
      this.perspCamera.updateProjectionMatrix();
      // The camera distance sets the perspective horizon, so re-cull glyphs.
      this.board?.orient?.(this.board.quaternion, this.perspCamera.position);
    }
    this.dirty = true;
  }

  /** Cell under normalized device coords (-1..1), or null. On solids only
   * front faces are hit — back cells are culled from picking too. */
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
    // Advance any in-flight board animation (reveal ripple, flag pop, lose
    // shake); while one is running keep the loop dirty so it renders every
    // frame, then fall idle again when it settles.
    const animating = this.board?.tickAnimations(performance.now()) ?? false;
    if (this.dirty || animating) {
      this.renderer.render(this.scene, this.camera);
      this.dirty = animating;
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

/** The per-mode starting orientation (port of GameScreen3D._initial_rotation). */
export function initialOrientation(mode: string): Quaternion {
  const qx = (a: number) => new Quaternion().setFromAxisAngle(X_AXIS, a);
  const qy = (a: number) => new Quaternion().setFromAxisAngle(Y_AXIS, a);
  // flat-faced solids show only one face head-on; a 3/4 turn reveals three
  // faces at once
  if (["cube", "tetrahedron", "cubeframe", "steppedbipyramid"].includes(mode)) {
    return qx(-0.5).multiply(qy(0.6));
  }
  // a tetrahedron viewed down a 2-fold axis looks like a flat square; turn
  // to a vertex-first 3/4 view so the frame's gaps read clearly
  if (mode === "tetraframe") return qx(-0.62).multiply(qy(0.45));
  // the Klein bottle reads best from a 3/4 turn: the neck diving through the
  // body (the self-intersection) is then plainly visible
  if (surfaceOf(mode)?.key === "klein") return qx(-0.4).multiply(qy(0.6));
  // wrapped surfaces tilt by their SurfaceSpec hint (donut, cylinder, Möbius);
  // everything else faces straight on
  const tilt = viewHint(mode);
  return tilt != null ? qx(tilt) : new Quaternion();
}
