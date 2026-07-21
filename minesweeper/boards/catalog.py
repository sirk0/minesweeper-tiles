"""The menu catalog, derived from two small registries.

Everything the menu and CLI need -- MODE_LABELS, TILINGS, SURFACE_LABELS,
the geometry-first menu tables, MODES_3D -- is *derived* here from
SURFACE_SPECS and TILING_SPECS rather than hand-listed. Adding a periodic
tiling means adding one
ArchTiling row (in tilings.py) and one ARCH_PRESETS row (in presets.py);
adding a surface means adding one SurfaceSpec here plus a builder. See
AGENTS.md. A mode string is always ``surface.prefix + tiling.key`` unless
the tiling overrides it (a few legacy names do).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from minesweeper.boards._data import load
from minesweeper.boards.tilings import ARCH_TILINGS

# The pure-data leaves of this module (surface specs, the regular tiling specs,
# the menu taxonomy and its labels) live in data/catalog.json, the single
# source both the pygame and TypeScript front-ends read. The derivations
# (MODE_LABELS, TILINGS, MODES_3D, allows(), mode_for(), ...) stay in code here
# and mirror the TypeScript. See scripts/export_data.py.
_CATALOG = load("catalog")


@dataclass(frozen=True)
class SurfaceSpec:
    key: str                          # "flat" | "torus" | "cylinder" | "mobius"
    label: str                        # menu label, "Torus"
    prefix: str                       # mode = prefix + tiling.key by default
    is_3d: bool                       # rendered by GameScreen3D
    needs_mirror: bool                # seam reverses orientation: excludes
    #                                   chiral tilings (snub hexagonal)
    boundary_components: int | None   # topological invariant; None for flat
    tilt: float | None = None         # GameScreen3D initial x-rotation
    tilings: frozenset[str] | None = None  # restrict to these tiling keys;
    #                                        None means every tiling (default)


# The menu picks a group, then a tiling, then -- for the uniform and
# dual-uniform tilings -- a surface. Every such tiling wraps every
# surface, with one exception per handedness: 3.3.3.3.6 (snub hexagonal)
# and its dual (the floret pentagonal) are chiral (p6, no mirror or
# glide), so the orientation-reversing Mobius seam cannot glue them to
# themselves (needs_mirror gates them out). The sphere is its own group:
# none of these planar patterns can tile it (Euler's formula forces
# curvature in), so it offers spherical tilings instead. To add a surface
# (e.g. the Klein bottle) add a SurfaceSpec here and wire its builders.
def _surface_from_json(row: dict) -> SurfaceSpec:
    tilings = row["tilings"]
    return SurfaceSpec(
        key=row["key"],
        label=row["label"],
        prefix=row["prefix"],
        is_3d=row["is3d"],
        needs_mirror=row["needsMirror"],
        boundary_components=row["boundaryComponents"],
        tilt=row["tilt"],
        tilings=frozenset(tilings) if tilings is not None else None,
    )


SURFACE_SPECS = tuple(_surface_from_json(r) for r in _CATALOG["surfaces"])
SURFACES = {s.key: s for s in SURFACE_SPECS}
SURFACE_LABELS = {s.key: s.label for s in SURFACE_SPECS}


@dataclass(frozen=True)
class TilingSpec:
    """A periodic tiling as the menu sees it. Regular tilings (square,
    triangle, hexagon) are declared explicitly below; Archimedean ones
    are lifted from tilings.ARCH_TILINGS."""
    key: str
    label: str
    chiral: bool = False                 # no mirror/glide -> no Mobius seam
    mode_overrides: dict = field(default_factory=dict)  # surface -> mode string

    def mode(self, surface: SurfaceSpec) -> str:
        return self.mode_overrides.get(surface.key, surface.prefix + self.key)

    def allows(self, surface: SurfaceSpec) -> bool:
        if surface.needs_mirror and self.chiral:
            return False
        if surface.tilings is not None and self.key not in surface.tilings:
            return False
        return True


# The three regular tilings keep their legacy mode names: the square
# tiling's wrapped boards are just the bare surface names, and the flat
# triangle grid is "trigrid". (Declared in data/catalog.json.)
REGULAR_TILINGS = tuple(
    TilingSpec(
        key=r["key"],
        label=r["label"],
        chiral=r["chiral"],
        mode_overrides=dict(r["modeOverrides"]),
    )
    for r in _CATALOG["regularTilings"]
)

TILING_SPECS = REGULAR_TILINGS + tuple(
    TilingSpec(t.key, t.label, chiral=t.template().mirror is None)
    for t in ARCH_TILINGS
)
TILINGS_BY_KEY = {t.key: t for t in TILING_SPECS}


def mode_for(tiling: str, surface: str) -> str:
    """The mode string for a (tiling, surface) pair, e.g.
    ('kagome', 'torus') -> 'toruskagome'. The one place the naming
    convention lives; the wrap builders and presets go through it."""
    return TILINGS_BY_KEY[tiling].mode(SURFACES[surface])


_MODE_SURFACE = {
    tiling.mode(surface): surface
    for tiling in TILING_SPECS
    for surface in SURFACE_SPECS
    if tiling.allows(surface)
}


def surface_of(mode: str) -> SurfaceSpec | None:
    """The SurfaceSpec a periodic (tiling x surface) mode lives on, or
    None for the one-off solids/aperiodic/shaped modes."""
    return _MODE_SURFACE.get(mode)


def view_hint(mode: str) -> float | None:
    """GameScreen3D initial x-rotation for a wrapped mode, or None if the
    mode is flat or a one-off solid (which set their own view)."""
    surface = surface_of(mode)
    return surface.tilt if surface else None


# tiling -> (label, {surface: mode}); the menu surface page reads this.
TILINGS = {
    t.key: (t.label, {s.key: t.mode(s) for s in SURFACE_SPECS if t.allows(s)})
    for t in TILING_SPECS
}

# ---------------------------------------------------------------------------
# Menu navigation taxonomy
#
# The menu is geometry-first: a five-item home page, each leading straight to a
# geometry (or a group of them) and then, where it applies, to a shared tiling
# picker.
#
#   Classic         -> flat squares, at once
#   Flat            -> tiling picker on the plane
#   Flat manifolds  -> plane / cylinder / Mobius / Klein / torus -> tiling picker
#   Sphere          -> the spherical tilings
#   Other           -> the solids, and the shaped boards
#
# The picker shows the three regular tilings directly, then the uniform, dual
# and (flat-only) aperiodic families as submenus, then a random option; it is
# parameterised by the surface it was reached through, so the same picker serves
# the plane and every flat manifold. Chiral tilings are gated out of the Mobius
# strip / Klein bottle per surface by TilingSpec.allows.
# ---------------------------------------------------------------------------

# The menu taxonomy and labels live in data/catalog.json (shared with the TS
# menu); the derivations below stay in code.
_MENU = _CATALOG["menu"]

# Home page: the five top-level entries, in order.
MENU_ROOT = tuple(_MENU["root"])
MENU_ROOT_LABELS = dict(_MENU["rootLabels"])

# Flat manifolds page: the wrappable surfaces (the plane first). The flat
# surface is labelled "Plane" here; picking any row opens the tiling picker.
MANIFOLD_ORDER = tuple(_MENU["manifoldOrder"])
MANIFOLD_LABELS = dict(_MENU["manifoldLabels"])

# The tiling picker: the three regular tilings are shown directly, then the
# uniform / dual / aperiodic families as submenus. The uniform and dual family
# members are exactly the Archimedean (vertex-transitive) tilings and their
# Laves duals, so they derive from ARCH_TILINGS -- adding a tiling stays a
# one-row change. Aperiodic tilings only wrap the plane, so that family is
# offered only when the surface is flat.
PICKER_REGULAR = tuple(_MENU["pickerRegular"])
UNIFORM_ARCH = tuple(t.key for t in ARCH_TILINGS if t.vertex_transitive)
DUAL_ARCH = tuple(t.key for t in ARCH_TILINGS if not t.vertex_transitive)
APERIODIC_MODES = tuple(_MENU["aperiodic"])
FAMILY_LABELS = dict(_MENU["familyLabels"])
FAMILY_MEMBERS = {
    "uniform": UNIFORM_ARCH,
    "dual": DUAL_ARCH,
    "aperiodic": APERIODIC_MODES,
}
# every tiling reachable through the picker (used for the random button)
PICKER_TILINGS = PICKER_REGULAR + UNIFORM_ARCH + DUAL_ARCH

# Sphere page: the spherical tilings, none of which wraps a flat surface.
SPHERE_MODES = tuple(_MENU["sphereModes"])

# Other page: the solids launch at once; "Shaped boards" opens the two shaped
# boards as a submenu.
OTHER_MODES = tuple(_MENU["otherModes"])
SHAPED_MODES = tuple(_MENU["shapedModes"])


def picker_modes(surface_key: str) -> tuple[str, ...]:
    """Every mode reachable on a surface through the tiling picker -- the pool
    the random button draws from (and the reachability guarantee in the tests).
    The flat picker also carries the aperiodic modes."""
    modes = [mode_for(t, surface_key) for t in PICKER_TILINGS
             if TILINGS_BY_KEY[t].allows(SURFACES[surface_key])]
    if surface_key == "flat":
        modes += list(APERIODIC_MODES)
    return tuple(dict.fromkeys(modes))


# The pool the random "Random tiling" button draws from on the plane: every
# flat tiling board (uniform, dual, and the aperiodic ones) -- no wrapped
# surfaces or solids.
FLAT_MODES = picker_modes("flat")

# Labels for the non-periodic (one-off) modes (aperiodic, sphere, solids,
# shaped) listed in the menu tuples above.
SOLO_LABELS = dict(_CATALOG["soloLabels"])

# mode -> label. Periodic modes take the tiling's label; the flat triangle
# grid keeps its own historical CLI label.
MODE_LABELS = {
    **{t.mode(s): t.label
       for t in TILING_SPECS for s in SURFACE_SPECS if t.allows(s)},
    "trigrid": "Triangle grid",
    **SOLO_LABELS,
}

_SOLID_MODES = frozenset(SPHERE_MODES) | frozenset(OTHER_MODES)
MODES_3D = frozenset(
    _SOLID_MODES
    | {t.mode(s) for t in TILING_SPECS for s in SURFACE_SPECS
       if s.is_3d and t.allows(s)}
)
