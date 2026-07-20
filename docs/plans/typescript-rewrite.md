# Minesweeper Tiles — TypeScript + Three.js rewrite

> Plan variant A: **new repo**. A sibling document,
> `typescript-rewrite-same-repo.md`, describes the alternative of hosting the
> TypeScript app inside the existing Python repo with shared JSON data files.
> Read both, pick one, execute.

## Context

The existing game (`sirk0/minesweeper-tiles`) is a Python/pygame minesweeper
over exotic boards: 105 modes (82 3D) — flat regular/Archimedean/Laves/
aperiodic tilings, spheres/fullerenes/polyhedra, torus/cylinder/Möbius/
Klein-bottle wrappings. Problems with the current app:

- **Web start is far too slow** — pygbag ships a CPython WASM runtime + pygame
  wheel (~15 MB) before the first frame. Inherent to the stack.
- **UI should look nicer** — flat-shaded software rasterizer, no GPU.
- **More platforms wanted** — web, iOS, macOS.

Decisions already made with the user:

- **Stack: TypeScript + Three.js (WebGL)** — sub-MB bundle, GPU rendering, one
  codebase.
- **New repo** (`sirk0/minesweeper-tiles-web`, user may rename); Python repo
  stays untouched as reference and conformance oracle.
- **Phased milestones**, each ending in a deployed playable build, until all
  105 modes are ported.
- **PWA first** for iOS/macOS (installable, offline); Capacitor later, out of
  scope.
- **Test automation is a first-class requirement**: unit tests (vitest) +
  Playwright e2e + screenshot image-comparison for boards and game screens
  (the Python project relied heavily on screenshots during development), with
  fixtures on both layers to keep test code small.

Porting scope: ~3,300 LOC pure dependency-free logic/geometry (mechanical
translation; no numpy anywhere), ~1,800 LOC pygame UI (redesigned, not
translated), 1,860 LOC Python tests whose invariants become the TS conformance
suite.

## New repo layout

Create `sirk0/minesweeper-tiles-web` via the GitHub API, develop on `main`
(Pages deploys from `main` via Actions).

```
minesweeper-tiles-web/
├── .github/workflows/ci.yml     # typecheck + unit + build + e2e/visual; Pages deploy on main
├── index.html                   # canvas + HTML overlay roots, iOS meta tags
├── package.json  tsconfig.json (strict, noUncheckedIndexedAccess)
├── vite.config.ts  playwright.config.ts  vitest.config.ts
├── public/
│   ├── icons/                   # 192/512/maskable/apple-touch-icon
│   └── fonts/                   # Rubik-Bold + DSEG7 woff2 (reuse assets from Python repo)
├── src/
│   ├── main.ts                  # bootstrap; reads ?mode=&difficulty=&seed= deep links
│   ├── game.ts                  # ← minesweeper/game.py
│   ├── rng.ts                   # seedable mulberry32
│   ├── testHook.ts              # window.__ms bridge (test builds/flag only)
│   ├── boards/
│   │   ├── core.ts              # ← boards/core.py (Board/Board3D, sharedVertexAdjacency,
│   │   │                        #   eulerCharacteristic/boundaryComponents, vec/mat math)
│   │   ├── tilings.ts           # ← boards/tilings.py (lattices + ArchTemplate + duals)
│   │   ├── aperiodic.ts         # ← boards/aperiodic.py (Penrose ℤ[ζ5], Hat metatiles)
│   │   ├── solids.ts            # ← boards/solids.py
│   │   ├── surfaces.ts          # ← boards/surfaces.py (immersions, wraps, cell_cycle)
│   │   ├── catalog.ts           # ← boards/catalog.py (SURFACE_SPECS/TILING_SPECS → 105 modes)
│   │   └── presets.ts           # ← boards/presets.py (buildBoard(mode, difficulty))
│   ├── render/
│   │   ├── renderer.ts          # scene/camera/resize/DPR; one pipeline flat & 3D
│   │   ├── boardMesh.ts         # polygons → beveled BufferGeometry, batching, picking
│   │   ├── glyphAtlas.ts        # canvas-baked digit/flag/mine texture atlas
│   │   ├── materials.ts         # onBeforeCompile: back-face dimming, hover highlight
│   │   └── animations.ts        # reveal ripple, flag pop, lose shake (test-disable flag)
│   ├── input/controls.ts        # pointer/touch/long-press, drag-rotate, wheel, keyboard
│   ├── ui/                      # hud.ts, menu.ts, dialogs.ts, styles.css (HTML overlay)
│   └── session.ts               # GameSession: Game ↔ mesh ↔ HUD ↔ Klein permutation
└── tests/
    ├── unit/                    # vitest: game, boards conformance (see Test strategy)
    ├── e2e/                     # Playwright specs + fixtures.ts
    ├── fixtures/                # shared JSON: mine layouts, mode lists, expected stats
    └── e2e/__screenshots__/     # committed visual baselines (linux-chromium)
```

`gui.py` is the only file with no 1:1 target — it dissolves into `render/`,
`input/`, `ui/`, `session.ts`. Everything else is near-mechanical translation
keeping names/structure so the codebases stay diffable.

## Key architectural decisions

- **Cell ids: canonical string keys.** Python's hashable tuples become
  `type CellId = string` via one encoder `cid(...parts)` (e.g. `"3,4"`,
  `"H1,3"`), used in `Map`/`Set`. Deterministic string sort replaces Python's
  tuple sort (order needs only determinism, not Python-identity).
- **Float-coincidence adjacency: centralized quantization.**
  `_shared_vertex_adjacency` (core.py:41) relies on `round(c, 6)` making
  floats coincide. Port as one `vkey(x,y[,z])` with
  `q = c => Math.round(c * 1e6) || 0` (`|| 0` kills `-0`). Nuance: several
  cell-id construction sites use their own precision (`round(gx, 3)`
  tilings.py:369, wrap rounding tilings.py:150, seam arithmetic
  tilings.py:498, Hat snap aperiodic.py:356) — port each verbatim per site;
  only shared-vertex adjacency goes through the global `vkey`.
- **Penrose arithmetic: plain `number`, not bigint.** ℤ[ζ5] coefficients grow
  ~φ² per deflation, far below 2^53 at preset depths; dev-mode
  `Number.isSafeInteger` assertion.
- **Renderer: one Three.js pipeline, merged BufferGeometry per board.** Flat
  boards = z=0 geometry + `OrthographicCamera`; 3D = `PerspectiveCamera` +
  custom ~50-line trackball (no OrbitControls). Each cell = inset top face +
  bevel ring quads (real geometry/normals → proper lighting). Triangulate with
  **earcut** (Hat is a non-convex 13-gon; project 3D polygons to Newell-normal
  plane first). One merged geometry, per-vertex color + face→cell table; state
  changes are ranged color-attribute updates; picking = raycast → faceIndex →
  cell. MSAA, `setPixelRatio(min(devicePixelRatio, 2))`. Two-sided/
  non-orientable: `DoubleSide` + `gl_FrontFacing` dimming shader chunk (keep
  opaque — transparency causes Möbius/Klein sort artifacts). Klein
  self-intersection handled correctly by the depth buffer. Lighting:
  directional + hemisphere.
- **Cell glyphs: canvas-baked texture atlas** (digits 1–8, flag, mine),
  batched UV quads in each cell's plane. One texture, ~2–3 draw calls/board.
  Rebake on DPR change.
- **UI chrome: HTML/CSS overlay** — menu drill-down (group → tiling → surface
  → difficulty), header (DSEG7 timer, flag counter, smiley reset), dialogs.
  Canvas owns only the board.
- **State: framework-free vanilla TS.** `game.ts` pure; each move returns the
  set of changed cells (enables ranged buffer updates + animations).
  `GameSession` mediates. No React.
- **Klein `cell_cycle` scroll = view-layer permutation** (`session.ts` holds
  offset `k`, renders through `cycle^k`, maps picks through the inverse;
  wheel/two-finger/`[`+`]`).
- **Deep links + determinism as a feature and a test seam:**
  `?mode=X&difficulty=Y&seed=N` starts a specific board with a seeded RNG.
  Built in M1 — Playwright navigates straight to any board, and screenshots
  are reproducible.
- **Bundle budget < 250 KB gz:** named ESM imports from `three`, earcut, no
  `examples/jsm`, no UI framework, woff2 subsets; `rollup-plugin-visualizer`
  soft budget check in CI.
- **RNG:** `mulberry32`, seedable; no attempt to clone Python's Mersenne
  stream — determinism via seeds and explicit `minePositions`.

## Test automation strategy

Three layers, fixtures at every layer, all in CI. Screenshots are the primary
review artifact during development (as in the Python repo) *and* a regression
gate.

### 1. Unit tests — vitest (`tests/unit/`)

**Game logic** (port of `tests/test_game.py`): explicit `minePositions` —
first-click safety (clicked cell only), flood fill, chording + abort on game
end, win auto-flag, flag counter, no-ops when not PLAYING/unknown cells,
constructor validation.

**Board conformance oracle** (port of `tests/test_boards.py`, expected values
copied verbatim from the Python tests — they are cross-language ground truth):
for every mode × difficulty via `buildBoard`:

- exact cell count and mine count;
- adjacency symmetry (`b ∈ adj(a) ⇔ a ∈ adj(b)`), no self-loops, all
  neighbors on board;
- Euler characteristic (2 for sphere topology, 0 for torus/Klein, per spec
  otherwise) and boundary-component counts per `SurfaceSpec`;
- `cell_cycle` is a bijective graph automorphism where present; triangle-Klein
  `tube ≡ 2 (mod 4)` rule;
- chirality gating (`allows()`), catalog completeness (105 modes, group
  membership, MODES_3D count).

**Vitest fixtures** (`test.extend` — vitest has Playwright-style fixtures):

- `boards` — memoized `buildBoard` cache so the 105×3 boards are each built
  once per run even though many test files assert on them (board construction
  is the expensive part; Python suite is sub-second, keep TS the same);
- `game` — factory fixture `game(layoutOrMines)` accepting explicit mine sets
  or a tiny ASCII-grid DSL for square boards, so game tests read as data;
- shared JSON in `tests/fixtures/` (mine layouts, per-mode expected stats
  exported once from the Python repo by a small script — commit the JSON, not
  the script's runtime).

### 2. End-to-end tests — Playwright (`tests/e2e/`)

Run against the production build (`vite preview` via `webServer` in
`playwright.config.ts`), Chromium project only (WebKit optional later for iOS
confidence).

**App test seam** (small, explicit, shipped behind a `?seed=`/test flag):

- deep links `?mode=&difficulty=&seed=` (deterministic board + mines);
- `window.__ms` hook exposing: `cellScreenXY(cellId)` (canvas has no DOM per
  cell — the app must translate cell → current screen coords, valid for flat
  and current 3D rotation), `setMines([...])`, `state()` summary
  (game state, flags, revealed count), `setRotation(q)`, `animations(false)`.
  This is the bridge that makes canvas games testable; keep it tiny and typed.

**Playwright fixtures** (`tests/e2e/fixtures.ts`, via `test.extend`):

- `gamePage` — navigates with base URL + seed, waits for first rendered frame
  (app sets `data-ready` on `<body>`), disables animations, fails the test on
  any console error;
- `board(mode, difficulty, mines?)` — deep-links to a board, optionally
  injects a fixture mine layout; returns helpers `reveal(cellId)`,
  `flag(cellId)` (right-click / long-press variant), `chord(cellId)`,
  `rotate(dx,dy)`, `kleinScroll(n)` — all implemented through
  `cellScreenXY` + mouse/touch primitives;
- `snap(name)` — standardized screenshot helper (fixed viewport 900×700,
  `deviceScaleFactor: 2`, masks the HTML timer, waits for idle) so every
  visual assertion is one line.

**Flow specs** (representative modes, not all 105 — the conformance suite owns
breadth):

- menu drill-down: group → tiling → surface → difficulty reaches a game for
  one mode per group; back navigation;
- play to **win** and to **lose** on a small square board with fixture mines;
  timer starts/stops, flag counter, smiley states, restart;
- chord and flood-fill behaviour driven through real clicks;
- 3D: drag rotates (screenshot before/after differs), click-vs-drag threshold
  (a drag must not reveal), keyboard rotate;
- Klein bottle: wheel scroll walks the cell cycle (a revealed cell's glyph
  moves; state preserved);
- touch emulation: long-press flags, tap reveals (mobile viewport project);
- PWA: manifest present, service worker registers, page reloads offline
  (`context.setOffline(true)`).

### 3. Visual regression — Playwright `toHaveScreenshot` image comparison

The Python workflow leaned on screenshots to judge boards; here they become
automated baselines:

- **Board gallery spec:** one screenshot per representative board —
  every distinct renderer path rather than all 105 modes: square/hex/tri flat,
  one Archimedean (snub-square), one Laves dual, Penrose, Hat, sphere, c80,
  cube, tetra-frame, torus-hex, cylinder, Möbius (two-sided dimming visible),
  Klein at scroll 0 and scrolled — each at a **fixed seed, fixed rotation,
  fixed viewport, animations off**;
- **Game-screen states:** revealed numbers 1–8 (crafted mine fixture), flags,
  win screen (auto-flagged), lose screen (exploded mine highlighted), menu
  pages (each group page, difficulty page);
- **Determinism policy:** WebGL output varies across GPUs/drivers, so
  baselines are only compared in one environment — CI's Linux Chromium forced
  to software rendering (launch args `--use-angle=swiftshader`), which is
  deterministic. Locally the same screenshots render for eyeballing, but
  comparison runs with `maxDiffPixelRatio: 0.01` and is authoritative only in
  CI (or a container matching it). Baselines live in
  `tests/e2e/__screenshots__/` (committed); updates via a manually-triggered
  `--update-snapshots` CI job (or locally in the devcontainer) with the diff
  visible in the PR.
- On failure CI uploads Playwright's actual/expected/diff triptych as an
  artifact — this doubles as the "progress screenshot" review artifact for
  every PR that touches rendering.

### CI pipeline (`.github/workflows/ci.yml`)

PRs and main: `tsc --noEmit` → `vitest run` → `vite build` → Playwright e2e +
visual (software-WebGL Chromium; cache `~/.cache/ms-playwright`) → bundle-size
check. On `main` after green: deploy `dist/` to Pages
(`actions/upload-pages-artifact` + `deploy-pages`). Failure artifacts: vitest
output, Playwright HTML report + screenshot diffs.

## Milestones (each ends deployed + playable; tests land with the code, not after)

- **M0 — Scaffold + pipeline proof.** Vite + strict TS, vitest, Playwright
  wired (one smoke e2e + one `toHaveScreenshot` on a hard-coded beveled square
  grid with hover + atlas glyphs), CI + Pages deploy, PWA shell
  (vite-plugin-pwa, manifest, icons, precache). De-risks render stack *and*
  the visual-test determinism (software WebGL) before any porting.
- **M1 — Core game + flat regular boards.** `game.ts`, `rng.ts`, `core.ts`,
  regular lattices (square/tri/hex/hexhex/triangle), input (mouse + touch
  long-press + chord), HUD + minimal menu, deep links + `window.__ms` seam.
  Tests: full game-logic suite, conformance for the 6 flat modes, win/lose
  e2e flows, first board-gallery baselines. Ships 6 modes, installable PWA.
- **M2 — 3D renderer + solids.** `solids.ts`, perspective camera, lighting,
  trackball + keyboard rotate, two-sided shader, touch state machine
  (tap/long-press/drag). Tests: solids conformance, rotate e2e,
  3D gallery baselines. Ships 16 modes.
- **M3 — Surface wraps (regular tilings).** `surfaces.ts` (torus/cylinder/
  Möbius/Klein × square/tri/hex), Klein scroll UI, surface menu page. Tests:
  Euler/boundary/cell-cycle conformance, Klein scroll e2e, wrap baselines.
  Ships 28 modes; hardest renderer risks retired.
- **M4 — Archimedean template engine + duals.** Rest of `tilings.ts`
  (ArchTemplate, 11 templates, dualTemplate, chirality gating), ARCH_PRESETS,
  full catalog. Tests: full-catalog conformance (105-mode counts now
  asserted), menu e2e per group. Ships 103 modes.
- **M5 — Aperiodic.** `aperiodic.ts` (Penrose ℤ[ζ5] deflation, Hat
  substitution + snap). Conformance + Penrose/Hat baselines. **All 105 modes.**
- **M6 — Polish.** Animations (with test-disable flag), affordances, iOS
  install audit (splash, safe-area, standalone), Lighthouse PWA pass, bundle
  audit, README + screenshots (generated by the Playwright gallery spec).

## GitHub Pages + PWA specifics

- Vite `base: '/minesweeper-tiles-web/'`; manifest `start_url`/`scope` and SW
  registration must agree with the base.
- `vite-plugin-pwa`, `registerType: 'autoUpdate'`, Workbox precache of all
  assets — zero runtime network needs → fully offline.
- iOS: apple-touch-icon, `viewport-fit=cover` + safe-area CSS,
  `-webkit-touch-callout: none` + `touch-action: none` on canvas (long-press
  flag must not trigger the callout), `contextmenu` prevented (right-click =
  flag). No install prompt on iOS → "Share → Add to Home Screen" hint dialog.

## Risks / gotchas

- Trig last-ulp drift vs CPython is ~9 orders below the 1e-6 quantization —
  keep formulas textually identical; Euler/boundary tests catch typos.
- Neighbor-order assumptions: none in game.py; `_tangent_order` is
  angle-based, fine — but audit while porting.
- Touch disambiguation (tap/long-press/drag) is the main mobile-feel risk —
  dedicated state machine in `controls.ts`, e2e-covered in M2.
- Visual-test flake: only compare screenshots in the pinned CI environment
  (software WebGL); everywhere else they're advisory.

## Verification (per milestone)

`vitest run` + `vite build` + `npx playwright test` locally (in Claude cloud
sessions Chromium is preinstalled at `/opt/pw-browsers/chromium` — use
`executablePath`, do not `playwright install`); eyeball the gallery
screenshots; push and confirm the Pages workflow is green, the deployed URL
loads fast, and bundle size is within the 250 KB gz budget. Cross-check board
stats against the Python repo by running its `.venv/bin/pytest` where needed.
