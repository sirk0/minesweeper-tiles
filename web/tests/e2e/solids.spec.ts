import { expect, test, type Page } from "@playwright/test";

// M2: the 3D solids — rotation (drag + keyboard), the click-vs-drag
// threshold, picking through the current rotation, and the menu groups.

async function shot(page: Page): Promise<Buffer> {
  await page.waitForTimeout(120);
  return page.screenshot();
}

/** A cell currently facing the camera, with its screen coords. */
async function visibleCell(
  page: Page,
): Promise<{ cell: string; x: number; y: number }> {
  const found = await page.evaluate(() => {
    const ms = window.__ms!;
    for (const cell of ms.cells()) {
      const xy = ms.cellScreenXY(cell);
      if (xy && xy.x > 250 && xy.x < 650 && xy.y > 200 && xy.y < 550) {
        return { cell, x: xy.x, y: xy.y };
      }
    }
    return null;
  });
  expect(found, "no visible cell found").not.toBeNull();
  return found!;
}

test.describe("M2 solids", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
  });

  test("menu lists the Sphere and Other groups and launches a solid", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    await expect(page.locator(".menu-subtitle", { hasText: "Sphere" })).toBeVisible();
    await expect(page.locator(".menu-subtitle", { hasText: "Other" })).toBeVisible();
    await page.locator('.menu-entry[data-mode="sphere"]').click();
    const state = await page.evaluate(() => window.__ms!.state());
    expect(state.screen).toBe("game");
    expect(state.mode).toBe("sphere");
    expect(state.is3d).toBe(true);
    expect(state.cellCount).toBe(60);
  });

  test("a plain click reveals; a drag rotates without revealing", async ({ page }) => {
    await page.goto("/?mode=cube&difficulty=easy&seed=5");
    await expect(page.locator("body[data-ready]")).toBeVisible();

    // Drag first: the view changes but nothing is revealed.
    const before = await shot(page);
    await page.mouse.move(450, 350);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(450 + 12 * i, 350 + 5 * i);
    await page.mouse.up();
    const after = await shot(page);
    expect(after.equals(before), "drag did not rotate the view").toBe(false);
    let state = await page.evaluate(() => window.__ms!.state());
    expect(state.revealed).toBe(0);

    // A stationary click on a visible cell reveals it.
    const target = await visibleCell(page);
    await page.mouse.click(target.x, target.y);
    state = await page.evaluate(() => window.__ms!.state());
    expect(state.revealed).toBeGreaterThan(0);
  });

  test("arrow keys rotate the board", async ({ page }) => {
    await page.goto("/?mode=sphere&difficulty=easy&seed=1");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    const before = await shot(page);
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowUp");
    const after = await shot(page);
    expect(after.equals(before), "keys did not rotate the view").toBe(false);
  });

  test("cells on the far side have no screen position until rotated around", async ({ page }) => {
    await page.goto("/?mode=sphere&difficulty=easy&seed=1");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    const { front, back, cells } = await page.evaluate(() => {
      const ms = window.__ms!;
      const cells = ms.cells();
      const front = cells.filter((c) => ms.cellScreenXY(c) != null);
      return { front: front.length, back: cells.length - front.length, cells: cells.length };
    });
    expect(front).toBeGreaterThan(0);
    expect(back).toBeGreaterThan(0);
    expect(front + back).toBe(cells);

    // A half-turn brings (roughly) the far side around: some previously
    // hidden cell becomes visible.
    const hiddenBefore = await page.evaluate(() => {
      const ms = window.__ms!;
      return ms.cells().filter((c) => ms.cellScreenXY(c) == null);
    });
    await page.evaluate(() => window.__ms!.rotate(Math.PI / 0.008, 0));
    const nowVisible = await page.evaluate(
      (hidden) => hidden.filter((c) => window.__ms!.cellScreenXY(c) != null),
      hiddenBefore,
    );
    expect(nowVisible.length).toBeGreaterThan(0);
  });

  test("flag and win flow on a solid", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    // One mine on a known cube cell; reveal every other cell wins.
    await page.evaluate(() => {
      const ms = window.__ms!;
      ms.startBoard("cube", "easy", { mines: ["0,-1,0,0"] });
      for (const cell of ms.cells()) {
        if (cell !== "0,-1,0,0") ms.reveal(cell);
      }
    });
    const state = await page.evaluate(() => window.__ms!.state());
    expect(state.status).toBe("won");
    expect(state.minesRemaining).toBe(0);
    await expect(page.locator(".hud-smiley")).toHaveText("😎");
  });

  for (const mode of [
    "sphere",
    "c80",
    "c180",
    "spheretri",
    "snubdodec",
    "cube",
    "cubeframe",
    "tetrahedron",
    "tetraframe",
    "steppedbipyramid",
  ]) {
    test(`${mode} reveals on a real click`, async ({ page }) => {
      await page.goto(`/?mode=${mode}&difficulty=easy&seed=2`);
      await expect(page.locator("body[data-ready]")).toBeVisible();
      const target = await visibleCell(page);
      await page.mouse.click(target.x, target.y);
      const state = await page.evaluate(() => window.__ms!.state());
      expect(state.revealed, `${mode}: click revealed nothing`).toBeGreaterThan(0);
    });
  }

  test("long-press flags on touch without rotating", async ({ page }) => {
    await page.goto("/?mode=cube&difficulty=easy&seed=5");
    await expect(page.locator("body[data-ready]")).toBeVisible();
    const target = await visibleCell(page);
    // Synthesize a stationary touch press held past the long-press delay.
    const client = await page.context().newCDPSession(page);
    await client.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [{ x: target.x, y: target.y }],
    });
    await page.waitForTimeout(700);
    await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    const state = await page.evaluate(() => window.__ms!.state());
    expect(state.minesRemaining).toBe(11); // one flag planted
    expect(state.revealed).toBe(0);
  });
});
