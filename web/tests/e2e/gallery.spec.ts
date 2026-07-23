import { expect, test } from "@playwright/test";

// Visual-regression gallery: one screenshot per distinct renderer path — the
// flat tiling shapes, then the M2 solids (curved pentagons, a Goldberg
// hex/pentagon mix, the cube's flat grid, and the two non-convex frame
// paths), each at its fixed per-mode starting rotation. Deterministic under
// software WebGL; only authoritative in the pinned CI environment.
const MODES = [
  "square",
  "trigrid",
  "hex",
  "triangle",
  "hexhex",
  "sphere",
  "c80",
  "cube",
  "tetraframe",
  "steppedbipyramid",
  // M3 wraps: the closed donut, the open two-sided cylinder, and the
  // non-orientable Möbius strip / Klein bottle (both drawn two-sided with the
  // back dimmed), each at its SurfaceSpec starting tilt.
  "torus",
  "cylinder",
  "mobius",
  "klein",
  // M5 aperiodic flat tilings: Penrose rhombi (thick/thin) and the Hat
  // monotile (a non-convex 13-gon), both trimmed to a square patch.
  "penrose",
  "hat",
];

test.describe("board gallery", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
  });

  for (const mode of MODES) {
    test(`${mode} board`, async ({ page }) => {
      await page.goto(`/?mode=${mode}&difficulty=easy&seed=1`);
      await expect(page.locator("body[data-ready]")).toBeVisible();
      await page.waitForTimeout(150);
      // No mask needed: with no interaction the timer never starts (reads 000).
      await expect(page).toHaveScreenshot(`board-${mode}.png`);
    });
  }

  test("revealed square with numbers, flag and exploded mine", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await page.evaluate(() => {
      const ms = window.__ms!;
      // A wall of mines across row 4 keeps the top from flooding into a win.
      const mines = Array.from({ length: 9 }, (_, c) => `4,${c}`);
      ms.startBoard("square", "easy", { mines });
      ms.reveal("0,0"); // floods rows 0-3, exposing numbers along row 3
      ms.flag("4,4"); // a correct flag on a mine
      ms.reveal("4,2"); // detonate a mine -> exploded + revealed mines
    });
    await page.waitForTimeout(150);
    // The game ends in a loss, which freezes the timer at 0s (reads 000), so
    // the shot is deterministic without masking.
    await expect(page).toHaveScreenshot("square-revealed.png");
  });

  test("revealed cube with numbers, a flag and an exploded mine", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await page.evaluate(() => {
      const ms = window.__ms!;
      // Mines along the top row of the front (+z) face; cells are
      // (axis, sign, i, j) with axis 2, sign 1 the front face.
      const mines = [0, 1, 2, 3].map((i) => `2,1,${i},3`);
      ms.startBoard("cube", "easy", { mines });
      // Reveal the numbered row under the mines one by one (each touches a
      // mine, so nothing floods), flag one mine, then detonate another.
      for (const i of [0, 1, 2, 3]) ms.reveal(`2,1,${i},2`);
      ms.flag("2,1,1,3"); // a correct flag on a mine
      ms.reveal("2,1,2,3"); // detonate -> exploded + revealed mines
    });
    await page.waitForTimeout(150);
    await expect(page).toHaveScreenshot("cube-revealed.png");
  });

  test("klein cell contents shift under scroll (offset 0 vs scrolled)", async ({ page }) => {
    // Reveal a spread of numbered cells on a dense-mine Klein board (each safe
    // cell borders a mine, so nothing cascades), then compare the board before
    // and after a scroll: the same numbers appear on different faces, while the
    // geometry never moves. The timer is masked (revealing starts it).
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await page.evaluate(() => {
      const ms = window.__ms!;
      ms.startBoard("klein", "easy");
      const cells = ms.cells();
      const n = cells.length;
      const safe = Array.from({ length: 8 }, (_, k) => cells[Math.floor((k * n) / 8)]!);
      const safeSet = new Set(safe);
      ms.startBoard("klein", "easy", { mines: cells.filter((c) => !safeSet.has(c)) });
      for (const c of safe.slice(0, 6)) ms.reveal(c);
    });
    const timer = page.locator('.hud-counter[data-slot="timer"]');
    await page.waitForTimeout(150);
    await expect(page).toHaveScreenshot("klein-revealed.png", { mask: [timer] });
    await page.evaluate(() => window.__ms!.scroll(1));
    await page.waitForTimeout(150);
    await expect(page).toHaveScreenshot("klein-scrolled.png", { mask: [timer] });
  });

  test("sphere glyphs stay on the visible hemisphere", async ({ page }) => {
    // Flagging every cell makes any glyph that leaks past the silhouette onto
    // the back surface plainly visible — the regression guard for the
    // perspective-correct glyph cull.
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await page.evaluate(() => {
      const ms = window.__ms!;
      ms.startBoard("sphere", "easy"); // build it first to enumerate cells
      const cells = ms.cells();
      ms.startBoard("sphere", "easy", { mines: cells.slice(0, 7) });
      for (const c of cells) ms.flag(c);
    });
    await page.waitForTimeout(150);
    await expect(page).toHaveScreenshot("sphere-flagged.png");
  });
});
