import { expect, test } from "@playwright/test";

// The rest of the suite runs under prefers-reduced-motion (animations off), so
// this spec flips them back on via the window.__ms.animations seam and drives a
// full flood + a detonation through the live render loop — a guard that the
// reveal ripple / flag pop / lose shake are purely cosmetic: gameplay reaches
// the same terminal state and the board settles without hanging the loop.
test.describe("M6 animations", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
  });

  test("a rippling flood still wins with animations enabled", async ({ page }) => {
    await page.evaluate(() => {
      const ms = window.__ms!;
      ms.animations(true);
      ms.startBoard("square", "easy", { mines: ["0,0"] });
      ms.reveal("8,8"); // floods the field, rippling outward
    });
    // Let the ripple play out; the win is immediate, the animation cosmetic.
    await page.waitForTimeout(500);
    const state = await page.evaluate(() => window.__ms!.state());
    expect(state.status).toBe("won");
    expect(state.revealed).toBe(80);
    await expect(page.locator(".hud-smiley")).toHaveText("😎");
  });

  test("a detonation shakes and still registers the loss", async ({ page }) => {
    await page.evaluate(() => {
      const ms = window.__ms!;
      ms.animations(true);
      ms.startBoard("square", "easy", { mines: ["4,4"] });
      ms.flag("2,2"); // a flag pop
      ms.reveal("4,4"); // detonate -> lose shake
    });
    await page.waitForTimeout(600); // outlast the shake
    const state = await page.evaluate(() => window.__ms!.state());
    expect(state.status).toBe("lost");
    await expect(page.locator(".hud-smiley")).toHaveText("😵");
  });
});
