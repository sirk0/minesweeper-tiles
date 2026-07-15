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
| `tilings.py` | Regular flat builders (square/triangle/hex/hexhex), the `_ArchTemplate` system, the eight `_*_template()` factories, and the **`ARCH_TILINGS`** registry (the one place an Archimedean tiling is declared). |
| `aperiodic.py` | Penrose (P3) and the Hat monotile, each with its own exact-arithmetic vertex ids. |
| `solids.py` | Closed/convex and polycube 3D boards (sphere, fullerenes, cube, tetrahedron, frames, bipyramid). |
| `surfaces.py` | Wrapping tilings onto surfaces: the three immersion points (`_torus_point`, `_cylinder_point`, `_mobius_point`), the shared `_assemble` tail, the nine simple `*_board` wrappers, and the Archimedean `arch_torus_board` / `arch_cylinder_board` / `arch_mobius_board`. |
| `catalog.py` | The menu, **derived**: `SURFACE_SPECS` and `TILING_SPECS` produce `MODE_LABELS`, `TILINGS`, `SURFACE_LABELS`, `GROUPS`, `MODES_3D`, `mode_for`, `surface_of`, `view_hint`. |
| `presets.py` | Difficulty presets and `build_board`. Regular/one-off modes are explicit; Archimedean modes come from the **`ARCH_PRESETS`** table. |

`__init__.py` re-exports the whole public surface, so `from
minesweeper.boards import ...` is unchanged by the split.

A **mode** is the string `build_board` takes. For a periodic tiling it is
`surface.prefix + tiling.key` (e.g. `toruskagome`); `catalog.mode_for`
is the only place that convention lives. Solids/aperiodic/shaped modes
are one-offs listed directly in `GROUPS` with labels in `SOLO_LABELS`.

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
   `presets.py` with `flat` / `torus` / `cylinder` / `mobius` args per
   difficulty. Omit `mobius` if the tiling is chiral. The build lambdas
   are generated for you.

That is it — no edits to `catalog.py`, `gui.py`, or the tests. The
board-shape convention (a flat board must read as a roughly *square*
rectangle, symmetric if the tiling is) is load-bearing: see the
`AGENT NOTE` comment in `tilings.py` and `archimedean_board`'s docstring.

## Recipe: add a Laves (dual / Catalan) tiling

Laves tilings are the **duals** of the Archimedean tilings: put a vertex
at each Archimedean tile centre and join centres of adjacent tiles. They
are periodic and edge-to-edge, so they use the *same* `ARCH_TILINGS`
registry, `_ArchTemplate` system, wrapping, presets and menu derivation
as the Archimedean tilings. Two things differ, and the architecture
already accounts for both:

- A Laves tiling is **face-transitive** (one congruent tile shape, but
  vertices of several kinds) rather than vertex-transitive. Declare it
  with `vertex_transitive=False` on its `ArchTiling` row. The
  vertex-configuration tests then skip it automatically, and
  `TestArchimedean.test_tiles_are_congruent` covers it instead (it checks
  every tile has the same edge/angle signature). `config` on the row
  should describe the single tile shape.
- Some Laves tilings' highest rotation centre sits on a **vertex**, not a
  tile centroid — pentagon-tiled ones (Cairo, floret, prismatic
  pentagonal) have no 2-fold centre inside a tile. For those, pass
  `centre=(x, y)` (domain coordinates of that rotation centre) to
  `_template(...)`; `archimedean_board` then centres its window there so
  the flat board comes out symmetric. Reflective vs chiral is derived from
  the template's mirror/glide, so no test list needs editing.

Steps:

1. Write `_foo_template()` in `tilings.py` giving one fundamental domain
   of the Laves tile polygons (optionally with `centre=`). You can derive
   the polygons by dualising the corresponding Archimedean template (tile
   centroids become vertices), or lay them out directly.
2. Add an `ArchTiling("foo", "Foo label", tile_config, edge_directions,
   _foo_template, vertex_transitive=False)` row to `ARCH_TILINGS`.
3. Add a `"foo"` block to `ARCH_PRESETS` (skip `mobius` if chiral — the
   floret pentagonal is).
4. Add the tiling's wrapped cell counts to
   `TestWrappedArchimedean.test_cell_counts` (that test asserts the count
   table matches the set of wrapped modes, so it fails until you do).

Everything else — menu, mode strings, `MODES_3D`, chirality gating,
symmetry and congruence invariants — derives automatically.

## Recipe: add an aperiodic / shaped / solid board

These are one-offs, not tiling×surface products.

1. Write a `*_board(...)` builder returning a `Board` (2D) or `Board3D`
   (3D). Flat float-coordinate builders should finish through
   `core._finalize_flat`; lattice builders through `core._build`; 3D
   builders assemble `cells` + `positions` and pick an orientation
   helper (`solids._convex_board3d` for convex solids, the polycube
   assemblers, or `surfaces._assemble`).
2. Add the mode to the right `GROUPS` entry and its label to
   `SOLO_LABELS` in `catalog.py`.
3. Add a `_PRESETS` block in `presets.py` (explicit lambdas).

## Recipe: add a surface (worked example — the Klein bottle)

A surface is a new column in the periodic tiling×surface grid. The
catalog derives everything from one `SurfaceSpec`, so the work is: an
immersion, a wrap builder, one spec row, and preset tuning.

1. **Immersion** in `surfaces.py`. A Klein bottle is a torus whose tube
   seam is glued with a flip, so use a figure-8 immersion, ``u`` around
   the ring and ``v`` around the cross-section (both radians):

   ```python
   def _klein_point(u: float, v: float, tube_radius: float = 0.45) -> Vec3:
       r = tube_radius
       across = r * math.cos(v)            # figure-8 cross-section
       fold = r * math.sin(v) * math.cos(u / 2)
       twist = r * math.sin(v) * math.sin(u / 2)
       radial = 1.0 + across
       return (radial * math.cos(u), radial * math.sin(u), fold + twist)
   ```

2. **Wrap builder** in `surfaces.py`, modelled on `arch_torus_board` but
   gluing the tube seam flipped after a full loop — reuse
   `template.mirror` exactly as `arch_mobius_board` does for its seam.
   Wrap the ring modulo like the torus and the tube with the mirror flip;
   assemble with `_assemble(..., two_sided=True, radius=_max_radius)`.
   A Klein bottle is closed (0 boundary circles) but non-orientable.

3. **SurfaceSpec** in `catalog.py`:

   ```python
   SurfaceSpec("klein", "Klein bottle", "klein", is_3d=True,
               needs_mirror=True, boundary_components=0, tilt=-0.9),
   ```

   `needs_mirror=True` makes the derivation drop the chiral snub
   hexagonal automatically, exactly like the Möbius strip.

4. **Presets** in `presets.py`: add `"klein": arch_klein_board` to
   `_ARCH_BUILDERS`, and a `"klein"` column to each tiling's
   `ARCH_PRESETS` block (skip snub hexagonal).

No menu, `gui.py`, or test edits are needed: `MODE_LABELS`, `TILINGS`,
`MODES_3D`, `mode_for`, `surface_of`, `view_hint` and the menu pages all
derive from the new `SurfaceSpec`, and the invariant/boundary tests pick
the new modes up automatically. If you add the spec but forget a preset,
`TestPresets.test_all_presets_build` fails loudly — that is the intended
guard rail.

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
