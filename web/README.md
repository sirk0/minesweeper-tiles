# Minesweeper Tiles — TypeScript + Three.js app (`web/`)

The in-progress TypeScript rewrite (Three.js / WebGL), living alongside the
Python game per `docs/plans/typescript-rewrite-same-repo.md`. This is **M0 —
scaffold + pipeline proof**: it renders a hard-coded beveled square grid with
hover picking and a glyph atlas, ships an installable PWA shell, and wires the
full test/CI pipeline. Board porting starts in M1.

## Commands

```sh
cd web
npm install
npm run dev         # Vite dev server
npm run typecheck   # tsc --noEmit (strict)
npm run test        # vitest unit tests
npm run build       # tsc + vite build (production bundle + PWA)
npm run e2e         # Playwright e2e + visual regression
npm run e2e:update  # refresh visual baselines
```

Cloud sessions: the preinstalled Chromium is used by pointing Playwright at it —
`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-<build>/chrome-linux/chrome npm run e2e`.

## Layout

- `src/render/` — one Three.js pipeline: `renderer.ts` (scene/ortho camera/
  resize/picking), `boardMesh.ts` (merged beveled-cell geometry, per-cell
  colours, hover), `glyphAtlas.ts` (canvas-baked digit/flag/mine texture),
  `demoBoard.ts` (the M0 hard-coded board).
- `src/ui/` — HTML/CSS overlay chrome: `hud.ts` (header) and `menu.ts` (home
  shell), both **rendered from the shared UI-screen config**.
- `src/config/screens.ts` — typed accessor over `../data/ui/screens.json`.
- `src/testHook.ts` — the tiny `window.__ms` seam Playwright drives.

## Shared configuration

UI-screen chrome (header slots, menu structure, difficulty rows, theme, smiley
faces) is declared once in **`data/ui/screens.json`** at the repo root and read
by both front-ends, so the pygame and TypeScript UIs can be kept in sync from a
single source rather than hand-matched. `src/config/screens.ts` gives the TS app
compile-time types over it. Later milestones extend the same shared-`data/`
approach to the board catalog and presets (see the plan).

## Deploy

CI (`.github/workflows/ci.yml`, `web` job) typechecks, unit-tests, builds and
runs the e2e/visual suite. During the transition GitHub Pages hosts both apps:
the pygbag build at the site root, this app under `/next/` (Vite `base` set from
`VITE_BASE` in `deploy-pages.yml`). Visual baselines are only authoritative in
the pinned CI environment (software WebGL / SwiftShader).
