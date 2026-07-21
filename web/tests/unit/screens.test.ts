import { describe, expect, it } from "vitest";
import { difficulty, screens } from "../../src/config/screens";

// Smoke + invariant tests for the shared UI-screen config. These guard the
// single source of truth the Python and TS front-ends share against structural
// drift.
describe("UI screen config", () => {
  it("loads with a version and theme", () => {
    expect(screens.version).toBeGreaterThan(0);
    expect(screens.theme.background).toMatch(/^#/);
  });

  it("has difficulties and a valid default", () => {
    expect(screens.difficulties.length).toBeGreaterThan(0);
    expect(() => difficulty(screens.defaultDifficulty)).not.toThrow();
  });

  it("every HUD slot declares a slot name", () => {
    const slots = [
      ...screens.hud.left,
      ...screens.hud.center,
      ...screens.hud.right,
    ];
    expect(slots.length).toBeGreaterThan(0);
    for (const s of slots) expect(s.slot).toBeTruthy();
  });

  it("menu root keys are unique and typed", () => {
    const keys = screens.menu.root.map((e) => e.key);
    expect(new Set(keys).size).toBe(keys.length);
    for (const e of screens.menu.root) {
      expect(["mode", "surface", "group"]).toContain(e.kind);
    }
  });

  it("provides all four smiley faces", () => {
    for (const face of ["playing", "won", "lost", "pressed"] as const) {
      expect(screens.smiley[face]).toBeTruthy();
    }
  });
});
