import { defineConfig, devices } from "@playwright/test";

// M0 e2e/visual proof. Runs against the production build via `vite preview`.
// Visual comparisons are only authoritative under deterministic software WebGL
// (SwiftShader) — the same launch args are used in CI so baselines match.
const PORT = 4173;

// In Claude cloud sessions Chromium is preinstalled; honour PLAYWRIGHT path env
// if set, otherwise let Playwright resolve its managed browser.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.05 },
  },
  use: {
    baseURL: `http://localhost:${PORT}/`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        deviceScaleFactor: 1,
        launchOptions: {
          ...(executablePath ? { executablePath } : {}),
          args: [
            "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader",
            "--ignore-gpu-blocklist",
          ],
        },
      },
    },
  ],
  webServer: {
    command: "npm run build && npm run preview -- --port " + PORT + " --strictPort",
    port: PORT,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
