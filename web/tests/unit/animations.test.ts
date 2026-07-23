import { describe, expect, it } from "vitest";
import {
  CellAnimations,
  RIPPLE_PER_CELL,
  rippleEntries,
} from "../../src/render/animations";

// The animation clock is pure timing (the meshes own the buffers), so it tests
// without a browser: drive it with explicit `now` values and read back the
// lightness / pop-scale / shake-offset it reports, plus the enabled gate the
// reduced-motion affordance and the window.__ms.animations seam flip.

describe("CellAnimations reveal flash", () => {
  it("stays dark until its staggered start, then peaks and settles to 0", () => {
    const a = new CellAnimations();
    a.startReveals([{ index: 0, delay: 100 }], 0);
    expect(a.lightness(0, 50)).toBe(0); // before its turn in the ripple
    expect(a.lightness(0, 100)).toBe(0); // exactly at start
    // Sample across the flash and take the brightest reading — a clear boost.
    const peak = Math.max(...[110, 130, 150, 170].map((t) => a.lightness(0, t)));
    expect(peak).toBeGreaterThan(0.15);
    expect(a.lightness(0, 100_000)).toBe(0); // long settled -> back to base
  });

  it("prunes a finished flash so step() redraws it exactly once at the end", () => {
    const a = new CellAnimations();
    a.startReveals([{ index: 3, delay: 0 }], 0);
    expect(a.step(10).recolor).toContain(3); // mid-flash: redraw
    expect(a.pending()).toBe(true);
    const settle = a.step(1000); // well past the flash
    expect(settle.recolor).toContain(3); // final redraw back to base
    expect(settle.active).toBe(false);
    expect(a.step(1001).recolor).not.toContain(3); // gone; nothing to draw
  });
});

describe("CellAnimations flag pop", () => {
  it("springs from 0 through an overshoot back to 1", () => {
    const a = new CellAnimations();
    expect(a.popScale(0, 0)).toBe(1); // no pop -> neutral scale
    a.startPop(0, 0);
    expect(a.popScale(0, 0)).toBeCloseTo(0, 1); // starts small
    const mid = a.popScale(0, 200);
    expect(mid).toBeGreaterThan(1); // overshoots past full size
    expect(a.popScale(0, 240)).toBe(1); // settled at the pop duration
    a.step(240); // prunes the finished pop
    expect(a.pending()).toBe(false);
  });
});

describe("CellAnimations shake", () => {
  it("offsets the board and decays back to rest", () => {
    const a = new CellAnimations();
    a.startShake(2, 0);
    expect(a.step(0).offset).toEqual([0, 0]); // sin(0) = 0
    const mid = a.step(20).offset;
    expect(Math.abs(mid[0])).toBeGreaterThan(0);
    const done = a.step(440); // shake duration
    expect(done.offset).toEqual([0, 0]);
    expect(a.pending()).toBe(false);
  });
});

describe("CellAnimations enabled gate", () => {
  it("ignores every trigger while disabled", () => {
    const a = new CellAnimations();
    a.enabled = false;
    a.startReveals([{ index: 0, delay: 0 }], 0);
    a.startPop(0, 0);
    a.startShake(2, 0);
    expect(a.pending()).toBe(false);
    expect(a.lightness(0, 10)).toBe(0);
    expect(a.popScale(0, 10)).toBe(1);
    expect(a.step(10).active).toBe(false);
  });
});

describe("rippleEntries", () => {
  it("delays each cell by its distance from the origin, in cell widths", () => {
    const cells = [
      { index: 0, center: [0, 0] },
      { index: 1, center: [10, 0] }, // 2 cell-widths away when unit = 5
    ];
    const entries = rippleEntries(cells, [0, 0], 5);
    expect(entries[0]!.delay).toBe(0);
    expect(entries[1]!.delay).toBeCloseTo(2 * RIPPLE_PER_CELL, 5);
  });

  it("fires everything at once when there is no origin", () => {
    const cells = [
      { index: 0, center: [0, 0] },
      { index: 1, center: [99, 99] },
    ];
    for (const e of rippleEntries(cells, null, 5)) expect(e.delay).toBe(0);
  });
});
