# Minesweeper Tiles — TypeScript + Three.js app (`web/`)

The in-progress TypeScript rewrite (Three.js / WebGL), living alongside the
Python game per `docs/plans/typescript-rewrite-same-repo.md`.

**M2 — 3D renderer + solids.** Ports the ten closed 3D boards (sphere,
snub dodecahedron, C80/C180 fullerenes, geodesic triangles, cube,
tetrahedron, cube frame, tetrahedron frame, stepped bipyramid) and adds the
3D half of the render pipeline: perspective camera, a custom trackball
(drag to rotate, arrow keys too), per-mode starting orientations, back-face
culling with an opaque base layer under the tile gaps, and a
`gl_FrontFacing` dimming shader ready for M3's two-sided surfaces. The
input state machine disambiguates tap / long-press / drag-rotate. 15 modes.

M0 (scaffold + pipeline proof: Vite, strict TS, PWA shell, CI/Pages) and M1
(core game rules, the five flat regular boards, HUD/menu from shared
config, deep links `?mode=&difficulty=&seed=`, the `window.__ms` test seam)
are the foundation this builds on. Boards are built from the **same**
`data/*.json` the Python game reads, and a conformance oracle
(`data/conformance.json`) asserts the two implementations produce identical
boards.

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

- `src/game.ts`, `src/rng.ts` — pure game rules (port of `game.py`) and a
  seedable RNG.
- `src/boards/` — `core.ts` (Board/Board3D, adjacency, topology, vector
  helpers), `tilings.ts` (the flat regular builders), `solids.ts` (the
  closed 3D boards), `catalog.ts` / `presets.ts` (read `data/*.json`).
- `src/render/` — one Three.js pipeline: `renderer.ts` (scene, ortho +
  perspective cameras, trackball rotation, resize, picking),
  `boardMesh.ts` (shared cell-visual vocabulary), `polygonBoard.ts` /
  `solidBoard.ts` (merged beveled cell geometry — flat plane vs. solid
  surface — per-cell colours, hover, glyph quads), `glyphAtlas.ts`
  (canvas-baked digit/flag/mine texture).
- `src/session.ts` — `GameSession`: Game ↔ mesh ↔ HUD.
- `src/input/controls.ts` — pointer/touch state machine (tap, long-press,
  right-click, drag-rotate on 3D boards).
- `src/ui/` — HTML/CSS overlay chrome: `hud.ts` (header) and `menu.ts` (home),
  both **rendered from the shared UI-screen config**.
- `src/config/screens.ts` — typed accessor over `../data/ui/screens.json`.
- `src/testHook.ts` — the `window.__ms` seam Playwright drives.

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
