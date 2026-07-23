import { expect, test } from "@playwright/test";

// Win and lose flows driven through the real renderer + input, with a fixture
// mine layout so the board is deterministic.
test.describe("M1 play", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
  });

  test("win: revealing the safe field wins and shows the cool smiley", async ({ page }) => {
    // One mine in the top-left corner; revealing the far corner floods the rest.
    await page.evaluate(() =>
      window.__ms?.startBoard("square", "easy", { mines: ["0,0"] }),
    );
    const xy = await page.evaluate(() => window.__ms?.cellScreenXY("8,8"));
    await page.mouse.click(xy!.x, xy!.y);
    const state = await page.evaluate(() => window.__ms?.state());
    expect(state?.status).toBe("won");
    expect(state?.minesRemaining).toBe(0);
    await expect(page.locator(".hud-smiley")).toHaveText("😎");
  });

  test("lose: revealing a mine loses and shows the dead smiley", async ({ page }) => {
    // Mine in the centre (clear of the HUD header) so the click lands on it.
    await page.evaluate(() =>
      window.__ms?.startBoard("square", "easy", { mines: ["4,4"] }),
    );
    const xy = await page.evaluate(() => window.__ms?.cellScreenXY("4,4"));
    await page.mouse.click(xy!.x, xy!.y);
    const state = await page.evaluate(() => window.__ms?.state());
    expect(state?.status).toBe("lost");
    await expect(page.locator(".hud-smiley")).toHaveText("😵");
  });

  test("lose: a flag on a safe cell is crossed out (renders without error)", async ({ page }) => {
    // One mine; flag a safe cell (a misplaced flag), then step on the mine.
    // On loss the safe flag is repainted as a crossed-out "wrongFlag" glyph.
    await page.evaluate(() =>
      window.__ms?.startBoard("square", "easy", { mines: ["4,4"] }),
    );
    await page.evaluate(() => window.__ms?.flag("0,0")); // safe cell -> wrong flag
    const xy = await page.evaluate(() => window.__ms?.cellScreenXY("4,4"));
    await page.mouse.click(xy!.x, xy!.y); // reveal the mine -> lost
    const state = await page.evaluate(() => window.__ms?.state());
    expect(state?.status).toBe("lost");
    await expect(page.locator(".hud-smiley")).toHaveText("😵");
  });

  test("flag counter and restart", async ({ page }) => {
    await page.evaluate(() =>
      window.__ms?.startBoard("square", "medium", { seed: 3 }),
    );
    await page.evaluate(() => window.__ms?.flag("5,5"));
    let state = await page.evaluate(() => window.__ms?.state());
    expect(state?.minesRemaining).toBe(39);
    await page.locator(".hud-smiley").click(); // restart
    state = await page.evaluate(() => window.__ms?.state());
    expect(state?.status).toBe("playing");
    expect(state?.minesRemaining).toBe(40);
  });
});
