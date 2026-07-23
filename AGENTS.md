# Extending the board zoo

This file is the map for adding tilings and surfaces. It is written for
AI agents first: every extension point is a single, named place, and the
test suite tells you the moment something is inconsistent. Read
`CLAUDE.md` for how to run the game, the tests, and the web build.

## The model in one paragraph

A board is a set of polygonal **cells**. Cell vertices are generated with
**exact, hashable ids** (integer lattice points in 2D, symbolic/float
keys in 3D) so that two cells are neighbours exactly when they share a
vertex id — no floating-point tolerance. `game.py` plays minesweeper over
that abstract adjacency graph and knows nothing about geometry. Never
introduce a vertex id that relies on rounding two nearby-but-distinct
points to the same key.

## Package layout (`minesweeper/boards/`)

Import order is a strict DAG; a module only imports from the ones above it.

| Module | Responsibility |
|--------|----------------|
| `core.py` | `Board` / `Board3D`, the `_shared_vertex_adjacency` neighbour rule, `_build` (lattice→pixels) and `_finalize_flat` (float→pixels), 3D vector helpers, and the topology invariants `euler_characteristic` / `boundary_components` / `corner_fans`. |
| `tilings.py` | Regular flat builders (square/triangle/hex/hexhex), the `_ArchTemplate` system, the eight Archimedean `_*_template()` factories plus their eight Laves duals (built by `_dual_template`), and the **`ARCH_TILINGS`** registry (the one place an Archimedean or Laves tiling is declared). |
| `aperiodic.py` | Penrose (P3) and the Hat monotile, each with its own exact-arithmetic vertex ids. |
| `solids.py` | Closed/convex and polycube 3D boards (sphere, fullerenes, cube, tetrahedron, frames, bipyramid). |
| `surfaces.py` | Wrapping tilings onto surfaces: the three immersion points (`_torus_point`, `_cylinder_point`, `_mobius_point`), the shared `_assemble` tail, the nine simple `*_board` wrappers, and the Archimedean `arch_torus_board` / `arch_cylinder_board` / `arch_mobius_board`. |
| `catalog.py` | The menu, **derived**: `SURFACE_SPECS` and `TILING_SPECS` (leaf data loaded from `data/catalog.json`) produce `MODE_LABELS`, `TILINGS`, `SURFACE_LABELS`, the geometry-first menu tables (`MENU_ROOT`/`MANIFOLD_*`/`FAMILY_*`/`SPHERE_MODES`/`OTHER_MODES`/`SHAPED_MODES`), `MODES_3D`, `mode_for`, `surface_of`, `view_hint`. |
| `presets.py` | Difficulty presets and `build_board`. Flat regular, solid, Archimedean/Laves and aperiodic (penrose/hat) presets all load from `data/presets.json` (shared with the web port). The Archimedean rows are authored in the compact **`ARCH_PRESETS`** table (tiling → surface → difficulty → args) that `scripts/export_data.py` expands into `data/presets.json`. |

`__init__.py` re-exports the whole public surface, so `from
minesweeper.boards import ...` is unchanged by the split.

### Shared JSON config (`data/*.json`) — single source of truth

A TypeScript/Three.js port of the game lives in `web/` (see
`docs/plans/typescript-rewrite-same-repo.md`). To keep the two
implementations from drifting, the *pure-data leaves* of the config live
in repo-root JSON that **both** front-ends read — so a value is never
written twice:

- `data/catalog.json` — `SURFACE_SPECS`, the regular `TilingSpec` rows,
  `DIFFICULTIES`, `SOLO_LABELS`, and the menu taxonomy/labels. `catalog.py`
  loads these via `boards/_data.py`; the *derivations* stay in code.
- `data/presets.json` — the difficulty presets for the **ported** modes
  (the flat regular ones — square/triangle/trigrid/hex/hexhex — the ten
  solids, the regular-tiling surface wraps, every Archimedean/Laves
  tiling × surface, and the two aperiodic tilings — penrose/hat), as
  `{mode: {builder, args}}`. The Archimedean/Laves rows carry the tiling
  key as their first arg. `presets.py` loads every row into `_PRESETS`
  via `_JSON_BUILDERS`; `_PRESETS` starts empty and holds only any
  still-unported one-offs. The Archimedean rows are generated from the
  compact `ARCH_PRESETS` table by `scripts/export_data.py`, so that table
  is their authoring source.
- `data/conformance.json` — board statistics (cell/mine/euler/boundary/…)
  per ported mode × difficulty, the TypeScript conformance oracle.

`scripts/export_data.py` and `scripts/export_conformance.py` regenerate
these from the Python side; the CI `data-sync` job re-runs them and fails
on any diff. `make web-prepare` copies `data/` into the pygbag stage so
the Python web build finds it at runtime.

A **mode** is the string `build_board` takes. For a periodic tiling it is
`surface.prefix + tiling.key` (e.g. `toruskagome`); `catalog.mode_for`
is the only place that convention lives. Solids/aperiodic/shaped modes
are one-offs listed directly in the `SPHERE_MODES` / `OTHER_MODES` /
`SHAPED_MODES` / `APERIODIC_MODES` tuples with labels in `SOLO_LABELS`.

## Recipe: add an Archimedean (periodic) tiling

Example goal: a new uniform tiling `foo` (say 3.4.6.4-like).

1. **Template** — write `_foo_template()` in `tilings.py` returning
   `_template(config, width, height, polygons, mirrored=?, glide=?)`.
   Supply one rectangular fundamental domain's cells as float-coordinate
   polygons. Copy the closest existing factory: `_kagome_template` is the
   simplest, `_snubsquare_template` shows the p4g `glide=True` case,
   `_snubhex_template` shows a chiral tiling (`mirrored=False`). Helpers
   `_hex_lattice_polygons`, `_regular_polygon`, `_square_on_edge` build
   hexagon-lattice tilings.
2. **Registry** — add one `ArchTiling("foo", "Foo label", config,
   edge_directions, _foo_template)` row to `ARCH_TILINGS`. This alone
   feeds `_ARCH_CONFIGS`, `_ARCH_TEMPLATES`, and — via `catalog` — the
   menu, mode strings, `MODES_3D`, and chirality gating (a tiling whose
   template has no mirror is automatically denied the Möbius strip).
3. **Presets** — add a `"foo": {...}` block to `ARCH_PRESETS` in
   `presets.py` with `flat` / `torus` / `cylinder` / `mobius` / `klein`
   args per difficulty. Omit `mobius` / `klein` if the tiling is chiral.
   Run `scripts/export_data.py` (and `export_conformance.py`) to expand it
   into `data/presets.json` (and refresh the oracle); both front-ends load
   from there.

That is it — no edits to `catalog.py`, `gui.py`, or the tests. The
board-shape convention (a flat board must read as a roughly *square*
rectangle, symmetric if the tiling is) is load-bearing: see the
`AGENT NOTE` comment in `tilings.py` and `archimedean_board`'s docstring.

## Recipe: add a Laves (dual / Catalan) tiling

Laves tilings are the **duals** of the Archimedean tilings: a vertex at
each Archimedean tile centre, joined across every shared edge. All eight
already ship (`_prismaticpent_template` … `_kisrhombille_template`), and
they use the *same* `ARCH_TILINGS` registry, `_ArchTemplate` system,
wrapping and presets as the Archimedean tilings. The `_dual_template`
helper builds one mechanically from its primal factory, deriving the tile
polygons (primal tile centres → dual vertices), the shared mirror/glide,
the `config` (the primal's vertex configuration — the Laves symbol), and
the flat-window `centre` (the primal's largest-tile centre, a rotation and
mirror centre of both tilings). So each factory is a one-liner. Two things
differ from an Archimedean tiling, both handled for you:

- A Laves tiling is **face-transitive** (one congruent tile shape, several
  vertex kinds) rather than vertex-transitive. Declare it with
  `vertex_transitive=False` on its `ArchTiling` row; the vertex-config
  tests then skip it, `TestArchimedean.test_tiles_are_congruent` covers it
  instead, and the catalog routes it into the **Dual-uniform tilings** menu
  submenu automatically (`DUAL_ARCH` is exactly the non-vertex-transitive
  `ARCH_TILINGS`, so no menu edit is needed).
- Its handedness (reflective vs chiral, hence Möbius or not) is read from
  the primal's mirror/glide automatically — the floret pentagonal (dual of
  snub hexagonal) is chiral, so like snub hexagonal it has no Möbius wrap.

Steps (say a new primal `_foo_template` gained a dual `_bar_template`):

1. `def _bar_template(): return _dual_template(_foo_template)` in
   `tilings.py`.
2. Add an `ArchTiling("bar", "Bar label", config, edge_directions,
   _bar_template, vertex_transitive=False)` row to `ARCH_TILINGS` (`config`
   is the Laves symbol, i.e. the primal's vertex configuration).
3. Add a `"bar"` block to `ARCH_PRESETS` (skip `mobius`/`klein` if chiral).
   The windows can copy the primal's — the dual shares its fundamental
   domain; only retune the mine counts to the dual's tile count.
4. Add the tiling's wrapped cell counts to
   `TestWrappedArchimedean.test_cell_counts` (that test asserts the count
   table matches the set of wrapped modes, so it fails until you do).

No `catalog.py` menu edit is needed — the Dual-uniform submenu derives from
`vertex_transitive`.

Everything else — mode strings, `MODES_3D`, chirality gating, symmetry and
congruence invariants — derives automatically.

## Recipe: add an aperiodic / shaped / solid board

These are one-offs, not tiling×surface products.

1. Write a `*_board(...)` builder returning a `Board` (2D) or `Board3D`
   (3D). Flat float-coordinate builders should finish through
   `core._finalize_flat`; lattice builders through `core._build`; 3D
   builders assemble `cells` + `positions` and pick an orientation
   helper (`solids._convex_board3d` for convex solids, the polycube
   assemblers, or `surfaces._assemble`).
2. Add the mode to the right menu tuple (`SPHERE_MODES`, `OTHER_MODES`,
   `SHAPED_MODES`, or `APERIODIC_MODES`) and its label to `SOLO_LABELS` in
   `catalog.py`.
3. Add the builder to `_JSON_BUILDERS` in `presets.py`, add a
   `{mode: {builder, args: {difficulty: [...]}}}` row to
   `data/presets.json` (positional args), and re-run
   `scripts/export_data.py` + `export_conformance.py`. This is what both
   front-ends read, so the mode is shared and the conformance oracle
   covers it. (A Python-only one-off can still go in `_PRESETS` as an
   explicit lambda, but the JSON path is preferred.)

## Recipe: add a surface (worked example — the Klein bottle)

A surface is a new column in the uniform/dual tiling×surface grid. The
catalog derives everything from one `SurfaceSpec`, so the work is: an
immersion, a wrap builder, one spec row, and preset tuning.

The Klein bottle is implemented **for every non-chiral tiling** — the
square (`klein_board`), the regular triangle/hexagon
(`klein_triangle_board`/`klein_hex_board`) and all 14 non-chiral template
tilings (`arch_klein_board`), plus the `"klein"` `SurfaceSpec`. The notes
below are its as-built documentation and the pattern for adding a fresh
surface.

1. **Immersion** in `surfaces.py`. A Klein bottle is a torus whose tube
   seam is glued with a flip. `_klein_point` uses the classic
   self-intersecting *bottle* immersion (`u` runs the profile round the
   ring — up the body, over the top, down and through the neck; `v` runs
   the circular cross-section, seam-reflected `v -> π - v`). It reads as
   the familiar bottle rather than a donut. It is piecewise (a `u < π`
   body branch, a `u ≥ π` neck branch) and its natural coordinates are
   large and off-origin, so every wrap builder **recentres** the sampled
   points (shared helper `_klein_recentre`) before `_assemble`
   (`GameScreen3D` measures `radius` from, and pivots rotation about, the
   origin, so off-origin geometry renders shrunk and off-centre). The
   neck-through-body self-intersection is unavoidable (no immersion of the
   Klein bottle embeds in 3-space) and lives on the `v ∈ {0, π}` circle;
   the builders offset `v` so no *vertex* lands there and all vertices
   stay distinct (`euler_characteristic`/`boundary_components` key on
   rounded coordinates — a merge silently drops χ below 0). A stray merge
   is a measure-zero coincidence that a small `tube`/`tube_scale` change
   clears, so presets are verified for χ = 0. An earlier figure-8
   (lemniscate) immersion is in the git history for the donut-shaped
   variant.

2. **Wrap builders** in `surfaces.py`. All are modelled on the torus
   builders: the cross-section (the tube) wraps straight, but the ring
   seam glues *flipped* — the tube re-enters reflected, so the surface is
   closed (0 boundary circles) yet non-orientable, hence drawn two-sided,
   not back-face culled. `_klein_recentre` + `radius=_max_radius` frame
   it. The flip needs an orientation-reversing tube mirror, so **chiral
   tilings are refused** (snub hexagonal, floret pentagonal), exactly as
   on the Möbius strip.

   - `klein_board` (square): vertex flip `j -> tube/2 - j - 1` (matching
     the immersion's `v -> π - v`, `tube` **even**); the *cell* flip is
     one lower because a cell is indexed by its low-`j` corner.
   - `klein_triangle_board`: splits each quad, diagonal alternating by
     column so the seam glide carries diagonals to diagonals — the ring
     translation is then an automorphism only when `tube` is 2 (mod 4)
     (else `cell_cycle` is `None`).
   - `klein_hex_board`: offset hex lattice, tube reflected `ky -> 4 - ky`
     across the ring seam (`rows` **even**).
   - `arch_klein_board`: the template version, next to `arch_torus_board`
     but gluing the seam flipped through `template.mirror` exactly as
     `arch_mobius_board` does. p4g (snub square, Cairo) has only a glide,
     so `nx` counts half-domains and must be **odd** there. The `+π/2`
     `v`-phase aligns the immersion's seam reflection with the tiling's
     tube mirror.

   `cell_cycle` is the one-step **ring translation** — a graph
   automorphism carried on `Board3D`. `GameScreen3D` reads it to let the
   player **scroll** the cell contents along the ring (mouse wheel /
   two-finger scroll), so cells hidden behind the self-intersection rotate
   into view without the geometry moving. The template/hex/triangle
   builders build it by matching each cell's shifted vertex set back to a
   generated cell (keeping it only when it is a bijection). Any board that
   exposes a `cell_cycle` gets the scrolling for free; everything else
   leaves it `None`.

3. **SurfaceSpec** in `catalog.py`:

   ```python
   SurfaceSpec("klein", "Klein bottle", "klein", is_3d=True,
               needs_mirror=True, boundary_components=0, tilt=-0.4),
   ```

   `needs_mirror=True` makes the derivation drop the chiral tilings
   automatically, exactly like the Möbius strip (`TilingSpec.allows`
   gates on it). A `SurfaceSpec` may also carry an optional
   `tilings=frozenset({...})` allow-list to restrict a *new* surface to
   specific tiling keys while its other wrap builders are still missing;
   the Klein bottle no longer needs one. The square tiling maps `(square,
   klein)` to the bare mode `"klein"` via its `mode_overrides`, like its
   other legacy surface names. Every klein mode also takes the `klein`
   3/4-view branch in `GameScreen3D._initial_rotation` (keyed on
   `surface_of(mode).key`), showing the self-intersection; `tilt` alone is
   only an x-rotation.

4. **Presets** in `presets.py`: explicit `"klein"`/`"kleintri"`/
   `"kleinhex"` blocks in `_PRESETS` for the regular tilings, `"klein":
   arch_klein_board` in `_ARCH_BUILDERS`, and a `"klein"` column in each
   non-chiral tiling's `ARCH_PRESETS` block (the non-glide ones reuse
   their `torus` `nx`/`ny`/mines; snub square and Cairo need odd `nx`).

One menu edit is needed: add the surface key to `MANIFOLD_ORDER` and a
label to `MANIFOLD_LABELS` in `catalog.py` so it appears (in your chosen
position) on the Flat manifolds page — that page lists its surfaces
explicitly. Everything else is still derived: `MODE_LABELS`, `TILINGS`,
`MODES_3D`, `mode_for`, `surface_of`, `view_hint`, the picker's per-surface
gating and the random pool all follow from the `SurfaceSpec`. The `klein`
modes join the wrapped-surface
invariant suite (`TestWrappedArchimedean` / `TestKleinTilings`) so
χ = 0 / 0 boundary circles are checked automatically; if you add the spec
but forget a preset, `TestPresets.test_all_presets_build` fails loudly.

## Verifying a change

- `make test` — the suite is sub-second. New boards are covered
  automatically: `TestInvariants` runs over every registered mode
  (adjacency symmetry, no self/duplicate neighbours, polygons in bounds,
  solvable mine counts), and for wrapped surfaces `TestWrappedArchimedean`
  checks the Euler characteristic (0) and that
  `boundary_components(board)` equals the surface's declared count.
- `make lint` — ruff (E/F/W/I; long geometry/table lines are allowed).
- Manual: `.venv/bin/python -m minesweeper` and walk the menu, or
  `.venv/bin/python -m minesweeper --mode <mode>` to jump straight in.
- Screenshot check for anything visual — see the headless recipe in
  `CLAUDE.md`. For a new tiling/surface, attach a screenshot to the PR.
