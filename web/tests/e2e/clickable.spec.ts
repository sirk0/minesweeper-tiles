import { expect, test } from "@playwright/test";

// Regression guard: every flat board must be playable via real clicks. This
// catches renderer/picking regressions like the one where large cells (triangle
// / trigrid) had bevels beyond the camera near plane, so the raycast could not
// reach them and clicks did nothing. Driving a real mouse click through
// cellScreenXY exercises the full project -> pick round-trip per board.
const MODES = ["square", "triangle", "trigrid", "hex", "hexhex"];

test.describe("every flat board is clickable", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
  });

  for (const mode of MODES) {
    test(`${mode} reveals on a real click`, async ({ page }) => {
      await page.goto("/");
      await expect(page.locator("body[data-ready]")).toBeVisible();

      // Build the board once to enumerate cells, then restart with a single
      // mine on the first cell and click a cell far from it.
      const target = await page.evaluate((mode) => {
        const ms = window.__ms!;
        ms.startBoard(mode, "easy");
        const cells = ms.cells();
        const mine = cells[0]!;
        const clickCell = cells[Math.floor(cells.length / 2)]!;
        ms.startBoard(mode, "easy", { mines: [mine] });
        return { xy: ms.cellScreenXY(clickCell), clickCell };
      }, mode);

      expect(target.xy, `${mode}: no screen coords for ${target.clickCell}`).not.toBeNull();
      await page.mouse.click(target.xy!.x, target.xy!.y);

      const state = await page.evaluate(() => window.__ms!.state());
      expect(state.revealed, `${mode}: click revealed nothing`).toBeGreaterThan(0);
    });
  }
});
