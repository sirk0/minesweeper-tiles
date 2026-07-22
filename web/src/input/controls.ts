import { Vector2 } from "three";
import type { CellId } from "../boards/core";

// Pointer/touch input for flat boards. Emits high-level gestures; the app maps
// them onto game actions. A tap that moves past the threshold or is held long
// becomes a long-press (mobile flag); right-click is a secondary (flag). The
// 3D drag-to-rotate state machine is added in M2.

const MOVE_THRESHOLD = 8; // px
const LONG_PRESS_MS = 450;

export interface ControlHandlers {
  pick(ndc: Vector2): CellId | null;
  onTap(cell: CellId): void;
  onLongPress(cell: CellId): void;
  onSecondary(cell: CellId): void;
  onHover(cell: CellId | null): void;
}

export function attachControls(
  canvas: HTMLCanvasElement,
  handlers: ControlHandlers,
): () => void {
  let downCell: CellId | null = null;
  let downX = 0;
  let downY = 0;
  let moved = false;
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
    downX = e.clientX;
    downY = e.clientY;
    moved = false;
    longFired = false;
    downCell = handlers.pick(ndc(e.clientX, e.clientY));
    if (downCell != null && e.pointerType !== "mouse") {
      const cell = downCell;
      longTimer = window.setTimeout(() => {
        longFired = true;
        handlers.onLongPress(cell);
      }, LONG_PRESS_MS);
    }
  };

  const onPointerMove = (e: PointerEvent) => {
    if (downCell != null && Math.hypot(e.clientX - downX, e.clientY - downY) > MOVE_THRESHOLD) {
      moved = true;
      clearLong();
    }
    if (e.pointerType === "mouse" && (e.buttons & 1) === 0) {
      handlers.onHover(handlers.pick(ndc(e.clientX, e.clientY)));
    }
  };

  const onPointerUp = (e: PointerEvent) => {
    clearLong();
    const cell = handlers.pick(ndc(e.clientX, e.clientY));
    if (!longFired && !moved && cell != null && cell === downCell) {
      handlers.onTap(cell);
    }
    downCell = null;
  };

  const onContextMenu = (e: MouseEvent) => {
    e.preventDefault();
    const cell = handlers.pick(ndc(e.clientX, e.clientY));
    if (cell != null) handlers.onSecondary(cell);
  };

  const onLeave = () => handlers.onHover(null);

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", () => {
    clearLong();
    downCell = null;
  });
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("contextmenu", onContextMenu);

  return () => {
    clearLong();
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    canvas.removeEventListener("pointerleave", onLeave);
    canvas.removeEventListener("contextmenu", onContextMenu);
  };
}
