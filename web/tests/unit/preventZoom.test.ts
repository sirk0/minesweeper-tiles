import { afterEach, describe, expect, it, vi } from "vitest";
import { preventDoubleTapZoom } from "../../src/input/preventZoom";

// The module listens on the global `document`; the unit env is plain node, so
// we stand in a tiny fake that records handlers and lets us fire synthetic
// touchend events at them.
type Handler = (e: unknown) => void;

function fakeDocument() {
  const handlers = new Map<string, Handler>();
  const doc = {
    addEventListener: (type: string, h: Handler) => handlers.set(type, h),
    removeEventListener: (type: string) => handlers.delete(type),
  };
  return { doc, handlers };
}

function touchEnd(timeStamp: number, x: number, y: number) {
  const e = {
    timeStamp,
    changedTouches: [{ clientX: x, clientY: y }],
    preventDefault: vi.fn(),
  };
  return e;
}

describe("preventDoubleTapZoom", () => {
  let dispose: (() => void) | null = null;
  const realDoc = (globalThis as { document?: unknown }).document;

  afterEach(() => {
    dispose?.();
    dispose = null;
    (globalThis as { document?: unknown }).document = realDoc;
  });

  function install() {
    const { doc, handlers } = fakeDocument();
    (globalThis as { document?: unknown }).document = doc;
    dispose = preventDoubleTapZoom();
    return handlers.get("touchend")!;
  }

  it("cancels the second tap of a fast same-spot double-tap", () => {
    const onTouchEnd = install();
    onTouchEnd(touchEnd(0, 100, 100));
    const second = touchEnd(150, 103, 98); // <300ms, <40px
    onTouchEnd(second);
    expect(second.preventDefault).toHaveBeenCalled();
  });

  it("leaves fast taps that land far apart alone (rapid reveals)", () => {
    const onTouchEnd = install();
    onTouchEnd(touchEnd(0, 100, 100));
    const second = touchEnd(120, 300, 260); // fast but >40px away
    onTouchEnd(second);
    expect(second.preventDefault).not.toHaveBeenCalled();
  });

  it("leaves slow taps in the same spot alone", () => {
    const onTouchEnd = install();
    onTouchEnd(touchEnd(0, 100, 100));
    const second = touchEnd(600, 100, 100); // same spot but >300ms
    onTouchEnd(second);
    expect(second.preventDefault).not.toHaveBeenCalled();
  });

  it("never cancels a lone tap", () => {
    const onTouchEnd = install();
    const first = touchEnd(500, 100, 100);
    onTouchEnd(first);
    expect(first.preventDefault).not.toHaveBeenCalled();
  });
});
