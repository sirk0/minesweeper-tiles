import { expect, test } from "@playwright/test";

// M3: the wrapped surfaces — the Flat-manifolds menu drill-down and the Klein
// bottle's cell-cycle scroll (a view-layer permutation that walks cell contents
// past the self-intersection while the game state and geometry stay put).

test.describe("M3 surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
  });

  test("Flat manifolds menu drills surface → tiling and launches a wrap", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await page.locator('.menu-entry[data-group="manifolds"]').click();
    await page.locator('.menu-entry[data-surface="torus"]').click();
    // back to the surface list, then in again — the breadcrumb works both ways
    await page.locator('.menu-entry[data-action="back"]').click();
    await page.locator('.menu-entry[data-surface="klein"]').click();
    await page.locator('.menu-entry[data-mode="kleinhex"]').click();
    const state = await page.evaluate(() => window.__ms!.state());
    expect(state.screen).toBe("game");
    expect(state.mode).toBe("kleinhex");
    expect(state.is3d).toBe(true);
  });

  // Reveal a spread of numbered cells on a dense-mine Klein board (each safe
  // cell borders a mine, so nothing cascades and the game stays in progress),
  // and return a currently front-facing revealed cell with its screen position.
  async function revealedTarget(page: import("@playwright/test").Page) {
    return page.evaluate(() => {
      const ms = window.__ms!;
      ms.startBoard("klein", "easy"); // enumerate the cells first
      const cells = ms.cells();
      const n = cells.length;
      const safe = Array.from({ length: 8 }, (_, k) => cells[Math.floor((k * n) / 8)]!);
      const safeSet = new Set(safe);
      const mines = cells.filter((c) => !safeSet.has(c));
      ms.startBoard("klein", "easy", { mines });
      const revealed = safe.slice(0, 6);
      for (const c of revealed) ms.reveal(c);
      const state = ms.state();
      const front = revealed
        .map((c) => ({ cell: c, xy: ms.cellScreenXY(c) }))
        .find((x) => x.xy != null);
      return { target: front ?? null, state };
    });
  }

  test("Klein scroll walks a revealed cell to a new position, game state intact", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    const { target, state } = await revealedTarget(page);
    expect(state.status).toBe("playing");
    expect(state.revealed).toBe(6);
    expect(target, "no front-facing revealed cell").not.toBeNull();

    const before = target!.xy!;
    const after = await page.evaluate((cell) => {
      const ms = window.__ms!;
      ms.scroll(1);
      return { xy: ms.cellScreenXY(cell), state: ms.state() };
    }, target!.cell);

    // The cell's contents moved to a different face: either it scrolled around
    // to the far side (no screen position) or to a visibly different spot.
    const moved = after.xy == null || Math.hypot(after.xy.x - before.x, after.xy.y - before.y) > 3;
    expect(moved, "the scrolled cell did not move").toBe(true);
    // The scroll is a pure view permutation — the game itself is untouched.
    expect(after.state.revealed).toBe(6);
    expect(after.state.status).toBe("playing");
    expect(after.state.minesRemaining).toBe(state.minesRemaining);
  });

  test("mouse wheel / two-finger scroll drives the Klein cell cycle", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    const { target } = await revealedTarget(page);
    expect(target, "no front-facing revealed cell").not.toBeNull();
    const before = target!.xy!;

    // A real wheel event over the board should step the ring (deltaY 160 > the
    // per-step threshold), exercising controls → app → session end to end.
    await page.mouse.move(450, 350);
    await page.mouse.wheel(0, 160);
    const after = await page.evaluate((cell) => window.__ms!.cellScreenXY(cell), target!.cell);
    const moved = after == null || Math.hypot(after.x - before.x, after.y - before.y) > 3;
    expect(moved, "wheel scroll did not move the cell").toBe(true);
  });

  test("a wrapped board has no cell cycle unless it is a Klein bottle", async ({ page }) => {
    await page.goto("/?mode=torus&difficulty=easy&seed=1");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    // The two Klein scroll controls are hidden on non-Klein surfaces.
    await expect(page.locator('.hud-btn[data-slot="klein-scroll-fwd"]')).toBeHidden();
    await page.goto("/?mode=klein&difficulty=easy&seed=1");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await expect(page.locator('.hud-btn[data-slot="klein-scroll-back"]')).toBeVisible();
    await expect(page.locator('.hud-btn[data-slot="klein-scroll-fwd"]')).toBeVisible();
  });
});
