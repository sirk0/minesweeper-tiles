import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { HapticKind } from "../../src/haptics";

// haptics dispatch picks its mechanism by feature detection at call time. The
// physical buzz can't be observed headless, but the dispatch is pure logic:
// with navigator.vibrate present we assert the pattern it's called with; with
// it absent we assert the iOS <input switch> fallback is created and clicked.
// The module reads ambient `navigator` / `document` globals and caches the
// switch element in a module-level singleton, so each test resets the module
// registry and re-imports, and stubs the globals via vi (node already defines a
// getter-only `navigator`, so plain assignment won't do).

async function loadHaptic(): Promise<(kind: HapticKind) => void> {
  vi.resetModules();
  return (await import("../../src/haptics")).haptic;
}

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("haptic() with the Vibration API", () => {
  it("fires a short single pulse for a placed flag", async () => {
    const vibrate = vi.fn();
    vi.stubGlobal("navigator", { vibrate });
    const haptic = await loadHaptic();
    haptic("flag");
    expect(vibrate).toHaveBeenCalledWith(15);
  });

  it("fires a heavier multi-pulse pattern on a loss", async () => {
    const vibrate = vi.fn();
    vi.stubGlobal("navigator", { vibrate });
    const haptic = await loadHaptic();
    haptic("lose");
    expect(vibrate).toHaveBeenCalledWith([40, 30, 40, 30, 80]);
  });
});

describe("haptic() iOS fallback (no Vibration API)", () => {
  function fakeDom() {
    const input = { type: "", setAttribute: vi.fn() };
    const label = {
      style: {} as Record<string, string>,
      setAttribute: vi.fn(),
      appendChild: vi.fn(),
      click: vi.fn(),
    };
    const createElement = vi.fn((tag: string) => (tag === "input" ? input : label));
    vi.stubGlobal("navigator", {}); // no vibrate
    vi.stubGlobal("document", { createElement, body: { appendChild: vi.fn() } });
    return { label, input, createElement };
  }

  it("builds a hidden switch and clicks it once for a flag", async () => {
    const { input, label } = fakeDom();
    const haptic = await loadHaptic();
    haptic("flag");
    expect(input.setAttribute).toHaveBeenCalledWith("switch", "");
    expect(label.click).toHaveBeenCalledTimes(1);
  });

  it("clicks repeatedly for a loss to feel stronger", async () => {
    vi.useFakeTimers();
    const { label } = fakeDom();
    const haptic = await loadHaptic();
    haptic("lose");
    expect(label.click).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(200);
    expect(label.click).toHaveBeenCalledTimes(3);
  });

  it("reuses the same switch element across calls", async () => {
    const { createElement } = fakeDom();
    const haptic = await loadHaptic();
    haptic("flag");
    haptic("flag");
    // Built once (label + input on the first call), then reused.
    expect(createElement).toHaveBeenCalledTimes(2);
  });
});
