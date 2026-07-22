import { expect, test } from "@playwright/test";

// Visual-regression gallery: one screenshot per flat renderer path (each tiling
// shape), plus a revealed-state shot. Deterministic under software WebGL; only
// authoritative in the pinned CI environment.
const MODES = ["square", "trigrid", "hex", "triangle", "hexhex"];

test.describe("M1 board gallery", () => {
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
});
