import { expect, test } from "@playwright/test";

// M0 pipeline proof: the app boots, the render seam is live, and the board
// renders deterministically (software WebGL) for the visual baseline.
test.describe("M0 smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
  });

  test("boots and exposes the test seam", async ({ page }) => {
    const summary = await page.evaluate(() => window.__ms?.state());
    expect(summary?.screen).toBe("game");
    expect(summary?.cells).toBe(64);
  });

  test("hover picking maps a cell to screen coords", async ({ page }) => {
    const xy = await page.evaluate(() => window.__ms?.cellScreenXY(0));
    expect(xy).not.toBeNull();
    await page.mouse.move(xy!.x, xy!.y);
    const hovered = await page.evaluate(() => window.__ms?.state().hovered);
    expect(hovered).toBe(0);
  });

  test("HUD header renders from config", async ({ page }) => {
    await expect(page.locator(".hud-smiley")).toBeVisible();
    await expect(page.locator('.hud-counter[data-slot="mine-counter"]')).toHaveText("010");
  });

  test("board renders (visual baseline)", async ({ page }) => {
    // Let the first frame settle before snapshotting.
    await page.waitForTimeout(200);
    await expect(page).toHaveScreenshot("demo-board.png", {
      mask: [page.locator('.hud-counter[data-slot="timer"]')],
    });
  });
});
