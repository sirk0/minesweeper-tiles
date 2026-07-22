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
});
