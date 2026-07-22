import { Vector2 } from "three";
import type { CellId } from "../boards/core";

// Pointer/touch input. Emits high-level gestures; the app maps them onto game
// actions. The gesture state machine disambiguates tap / long-press / drag:
// a press that stays put and is released is a tap (reveal); held long on
// touch it becomes a long-press (flag); moved past the threshold it becomes a
// drag, which rotates the board when the app says the current board rotates
// (3D) and otherwise cancels the tap. Right-click is a secondary (flag).

const MOVE_THRESHOLD = 8; // px
const LONG_PRESS_MS = 450;

export interface ControlHandlers {
  pick(ndc: Vector2): CellId | null;
  onTap(cell: CellId): void;
  onLongPress(cell: CellId): void;
  onSecondary(cell: CellId): void;
  onHover(cell: CellId | null): void;
  /** Whether drags should rotate the current board (a 3D screen). */
  rotates(): boolean;
  /** A drag step of (dx, dy) CSS pixels while rotating. */
  onRotate(dx: number, dy: number): void;
}

export function attachControls(
  canvas: HTMLCanvasElement,
  handlers: ControlHandlers,
): () => void {
  let pressed = false;
  let downCell: CellId | null = null;
  let downX = 0;
  let downY = 0;
  let lastX = 0;
  let lastY = 0;
  let moved = false;
  let rotating = false;
  let longTimer = 0;
  let longFired = false;

  const ndc = (clientX: number, clientY: number): Vector2 => {
    const r = canvas.getBoundingClientRect();
    return new Vector2(
      ((clientX - r.left) / r.width) * 2 - 1,
      -(((clientY - r.top) / r.height) * 2 - 1),
    );
  };

  const clearLong = () => {
    if (longTimer) window.clearTimeout(longTimer);
    longTimer = 0;
  };

  const onPointerDown = (e: PointerEvent) => {
    if (e.button === 2) return; // handled on contextmenu
    pressed = true;
    downX = lastX = e.clientX;
    downY = lastY = e.clientY;
    moved = false;
    rotating = false;
    longFired = false;
    downCell = handlers.pick(ndc(e.clientX, e.clientY));
    // keep receiving moves when a rotation drag leaves the canvas
    canvas.setPointerCapture?.(e.pointerId);
    if (downCell != null && e.pointerType !== "mouse") {
      const cell = downCell;
      longTimer = window.setTimeout(() => {
        longFired = true;
        handlers.onLongPress(cell);
      }, LONG_PRESS_MS);
    }
  };

  const onPointerMove = (e: PointerEvent) => {
    if (pressed && !longFired) {
      if (
        !moved &&
        Math.hypot(e.clientX - downX, e.clientY - downY) > MOVE_THRESHOLD
      ) {
        moved = true;
        clearLong();
        if (handlers.rotates()) rotating = true;
      }
      if (rotating) handlers.onRotate(e.clientX - lastX, e.clientY - lastY);
    }
    lastX = e.clientX;
    lastY = e.clientY;
    if (e.pointerType === "mouse" && (e.buttons & 1) === 0) {
      handlers.onHover(handlers.pick(ndc(e.clientX, e.clientY)));
    }
  };

  const onPointerUp = (e: PointerEvent) => {
    clearLong();
    const wasRotating = rotating;
    pressed = false;
    rotating = false;
    const cell = handlers.pick(ndc(e.clientX, e.clientY));
    if (!longFired && !moved && !wasRotating && cell != null && cell === downCell) {
      handlers.onTap(cell);
    }
    downCell = null;
  };

  const onContextMenu = (e: MouseEvent) => {
    e.preventDefault();
    const cell = handlers.pick(ndc(e.clientX, e.clientY));
    if (cell != null) handlers.onSecondary(cell);
  };

  const onCancel = () => {
    clearLong();
    pressed = false;
    rotating = false;
    downCell = null;
  };

  const onLeave = () => handlers.onHover(null);

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onCancel);
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("contextmenu", onContextMenu);

  return () => {
    clearLong();
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    canvas.removeEventListener("pointercancel", onCancel);
    canvas.removeEventListener("pointerleave", onLeave);
    canvas.removeEventListener("contextmenu", onContextMenu);
  };
}
