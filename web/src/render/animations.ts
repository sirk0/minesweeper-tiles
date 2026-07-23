// Board animations, shared by the flat PolygonBoard and the 3D SolidBoard.
//
// Three effects, all driven from a single clock the renderer ticks each frame
// while anything is pending (`step`); when nothing is pending the renderer
// leaves the loop idle (`pending`). The meshes own the buffers, so this class
// only tracks timing and returns, per frame, what changed:
//
//   * reveal ripple — each freshly opened cell flashes brighter than its
//     settled colour, staggered by its distance from the click so a wave
//     sweeps outward across a flood fill (the mesh recolours the reported
//     cells, adding `lightness`).
//   * flag pop — a placed flag's glyph springs in with a small overshoot
//     (the mesh rebuilds glyphs, scaling each by `popScale`).
//   * lose shake — the whole board jitters and settles when a mine detonates
//     (the mesh offsets its group position by `shakeOffset`).
//
// `enabled` gates every trigger, so turning it off (the `prefers-reduced-motion`
// affordance, or the `window.__ms.animations(false)` test seam) makes each
// board render its final state instantly and keeps the render loop idle.

/** Peak lightness boost of a reveal flash, in HSL L units (0..1). */
const PULSE_LIGHT = 0.35;
/** Reveal flash timing: rise to the peak, then fall back to the settled tone. */
const PULSE_RISE = 60; // ms
const PULSE_FALL = 260; // ms
/** Stagger added per cell-width of distance from the reveal origin. */
export const RIPPLE_PER_CELL = 28; // ms
/** Flag-pop duration. */
const POP_MS = 240;
/** Lose-shake duration and oscillation frequency. */
const SHAKE_MS = 440;
const SHAKE_HZ = 11;

/** What a single tick changed; the mesh applies it to its own buffers. */
export interface AnimStep {
  /** Cell indices whose reveal-flash lightness may have changed this frame
   * (includes cells whose flash just finished, so the mesh writes them back to
   * the settled colour exactly once). */
  recolor: number[];
  /** Whether a flag pop is in flight, so the mesh rebuilds its glyph quads. */
  glyphsDirty: boolean;
  /** Board position offset for the lose-shake (`[0, 0]` when not shaking). */
  offset: [number, number];
  /** Whether any animation still needs another frame after this one. */
  active: boolean;
}

interface Reveal {
  start: number; // when this cell's flash begins (origin time + stagger)
}

export class CellAnimations {
  enabled = true;
  private readonly reveals = new Map<number, Reveal>();
  private readonly pops = new Map<number, number>(); // cell index -> start time
  private shakeStart: number | null = null;
  private shakeAmp = 0;

  /** Begin reveal flashes for the given cells at their per-cell stagger. */
  startReveals(entries: { index: number; delay: number }[], now: number): void {
    if (!this.enabled) return;
    for (const e of entries) this.reveals.set(e.index, { start: now + e.delay });
  }

  /** Begin a flag pop on a cell. */
  startPop(index: number, now: number): void {
    if (!this.enabled) return;
    this.pops.set(index, now);
  }

  /** Begin a lose-shake of the given amplitude (in board world units). */
  startShake(amplitude: number, now: number): void {
    if (!this.enabled) return;
    this.shakeStart = now;
    this.shakeAmp = amplitude;
  }

  /** Drop every in-flight animation (used when a board is reset). */
  reset(): void {
    this.reveals.clear();
    this.pops.clear();
    this.shakeStart = null;
  }

  /** Whether the render loop needs to keep ticking this board. */
  pending(): boolean {
    return this.reveals.size > 0 || this.pops.size > 0 || this.shakeStart != null;
  }

  /** Extra HSL lightness for a cell's reveal flash right now (0 when idle). */
  lightness(index: number, now: number): number {
    const r = this.reveals.get(index);
    if (!r) return 0;
    const t = now - r.start;
    if (t <= 0) return 0; // still waiting its turn in the ripple
    if (t < PULSE_RISE) return PULSE_LIGHT * (t / PULSE_RISE);
    const f = t - PULSE_RISE;
    if (f < PULSE_FALL) return PULSE_LIGHT * (1 - f / PULSE_FALL);
    return 0;
  }

  /** Glyph scale for a cell's flag pop right now (1 when idle) — an
   * ease-out-back springing from 0 through a small overshoot to 1. */
  popScale(index: number, now: number): number {
    const start = this.pops.get(index);
    if (start === undefined) return 1;
    const t = now - start;
    if (t >= POP_MS) return 1;
    const p = t / POP_MS;
    const c = 1.7;
    const u = p - 1;
    return 1 + (c + 1) * u * u * u + c * u * u; // easeOutBack, 0 → ~1.1 → 1
  }

  /** Advance every animation to `now`, pruning finished ones, and report what
   * the mesh must redraw this frame. */
  step(now: number): AnimStep {
    const recolor: number[] = [];
    for (const [index, r] of this.reveals) {
      recolor.push(index); // active or just-finished: redraw once either way
      if (now - r.start >= PULSE_RISE + PULSE_FALL) this.reveals.delete(index);
    }

    const glyphsDirty = this.pops.size > 0;
    for (const [index, start] of this.pops) {
      if (now - start >= POP_MS) this.pops.delete(index);
    }

    const offset = this.shakeOffset(now);

    return { recolor, glyphsDirty, offset, active: this.pending() };
  }

  private shakeOffset(now: number): [number, number] {
    if (this.shakeStart == null) return [0, 0];
    const t = now - this.shakeStart;
    if (t >= SHAKE_MS) {
      this.shakeStart = null;
      return [0, 0];
    }
    const decay = 1 - t / SHAKE_MS;
    const s = Math.sin((t / 1000) * 2 * Math.PI * SHAKE_HZ) * this.shakeAmp * decay;
    return [s, s * 0.3];
  }
}

/** Turn a list of cells + their board-space centres into stagger entries for a
 * reveal ripple: delay grows with distance from `origin`, measured in cell
 * widths (`unit`), so the wave spreads at a steady visual speed on any board. */
export function rippleEntries(
  cells: { index: number; center: readonly number[] }[],
  origin: readonly number[] | null,
  unit: number,
): { index: number; delay: number }[] {
  return cells.map(({ index, center }) => {
    const d = origin ? distance(center, origin) : 0;
    return { index, delay: (d / unit) * RIPPLE_PER_CELL };
  });
}

function distance(a: readonly number[], b: readonly number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    sum += d * d;
  }
  return Math.sqrt(sum);
}
