import { expect, test } from "@playwright/test";

// Boot + menu navigation + the test seam.
test.describe("M1 app", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
  });

  test("starts on the menu with the HUD hidden", async ({ page }) => {
    await expect(page.locator(".menu-title")).toBeVisible();
    await expect(page.locator(".hud")).toBeHidden();
    const state = await page.evaluate(() => window.__ms?.state());
    expect(state?.screen).toBe("menu");
  });

  test("menu launches a flat board at the chosen difficulty", async ({ page }) => {
    await page.locator('.difficulty-btn[data-key="easy"]').click();
    await page.locator('.menu-entry[data-group="flat"]').click();
    await page.locator('.menu-entry[data-mode="square"]').click();
    const state = await page.evaluate(() => window.__ms?.state());
    expect(state?.screen).toBe("game");
    expect(state?.mode).toBe("square");
    expect(state?.difficulty).toBe("easy");
    expect(state?.cellCount).toBe(81); // 9x9 easy
    await expect(page.locator(".hud-smiley")).toBeVisible();
  });

  test("deep link starts a specific board", async ({ page }) => {
    await page.goto("/?mode=hex&difficulty=easy&seed=7");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    const state = await page.evaluate(() => window.__ms?.state());
    expect(state?.mode).toBe("hex");
    expect(state?.difficulty).toBe("easy");
    expect(state?.cellCount).toBe(99);
  });
});
