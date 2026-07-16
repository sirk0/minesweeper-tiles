"""The menu catalog, derived from two small registries.

Everything the menu and CLI need -- MODE_LABELS, TILINGS, SURFACE_LABELS,
GROUPS, MODES_3D -- is *derived* here from SURFACE_SPECS and TILING_SPECS
rather than hand-listed. Adding a periodic tiling means adding one
ArchTiling row (in tilings.py) and one ARCH_PRESETS row (in presets.py);
adding a surface means adding one SurfaceSpec here plus a builder. See
AGENTS.md. A mode string is always ``surface.prefix + tiling.key`` unless
the tiling overrides it (a few legacy names do).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from minesweeper.boards.tilings import ARCH_TILINGS


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
SURFACE_SPECS = (
    SurfaceSpec("flat", "Flat", "", is_3d=False, needs_mirror=False,
                boundary_components=None),
    SurfaceSpec("mobius", "Möbius strip", "mobius", is_3d=True,
                needs_mirror=True, boundary_components=1, tilt=-0.8),
    SurfaceSpec("cylinder", "Cylinder", "cyl", is_3d=True, needs_mirror=False,
                boundary_components=2, tilt=-0.35),
    SurfaceSpec("torus", "Torus", "torus", is_3d=True, needs_mirror=False,
                boundary_components=0, tilt=-1.0),
    # A Klein bottle: closed like the torus but glued with a flip, so
    # non-orientable, shaped as the classic self-intersecting bottle. Only
    # the square tiling wraps it for now. (GameScreen3D adds a y-turn on
    # top of this x-tilt so the neck-through-body view reads clearly.)
    SurfaceSpec("klein", "Klein bottle", "klein", is_3d=True,
                needs_mirror=True, boundary_components=0, tilt=-0.4,
                tilings=frozenset({"square"})),
)
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
# triangle grid is "trigrid".
REGULAR_TILINGS = (
    TilingSpec("square", "Squares", mode_overrides={
        "torus": "torus", "cylinder": "cylinder", "mobius": "mobius",
        "klein": "klein"}),
    TilingSpec("tri", "Triangles", mode_overrides={"flat": "trigrid"}),
    TilingSpec("hex", "Hexagons"),
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

# The two tiling groups route through a tiling then a surface. Each lists
# its tilings explicitly (the tiling pages), so the 11 uniform tilings and
# their 11 Laves duals form parallel menus. The three regular tilings are
# self/mutually dual (square is self-dual, triangle <-> hexagon), so they
# appear in both groups, reusing the same boards.
UNIFORM_TILINGS = (
    "square", "tri", "hex", "elongated", "snubsquare", "kagome", "snubhex",
    "truncsquare", "trunchex", "rhombitrihex", "trunctrihex",
)
DUAL_TILINGS = (
    "square", "hex", "tri", "prismaticpent", "cairo", "rhombille", "floret",
    "tetrakis", "triakis", "deltoidal", "kisrhombille",
)
GROUP_TILINGS = {"uniform": UNIFORM_TILINGS, "dual": DUAL_TILINGS}

# group -> (label, modes); the two tiling groups route through GROUP_TILINGS
# (empty modes here is the signal), the rest list their one-off modes.
GROUPS = {
    "uniform": ("Uniform tilings", ()),
    "dual": ("Dual-uniform tilings", ()),
    "aperiodic": ("Aperiodic", ("penrose", "hat")),
    "sphere": ("Sphere", ("sphere", "c80", "c180", "spheretri", "snubdodec")),
    "polyhedra": (
        "Polyhedra",
        ("cube", "tetrahedron", "tetraframe", "cubeframe", "steppedbipyramid"),
    ),
    "shaped": ("Shaped boards", ("triangle", "hexhex")),
}

# Labels for the non-periodic (one-off) modes listed in GROUPS.
SOLO_LABELS = {
    "penrose": "Penrose rhombi",
    "hat": "The Hat",
    "sphere": "60 pentagons",
    "c80": "C80 fullerene",
    "c180": "C180 fullerene",
    "spheretri": "Triangles",
    "snubdodec": "Snub dodecahedron",
    "cube": "Cube",
    "tetrahedron": "Tetrahedron",
    "tetraframe": "Tetrahedron frame",
    "cubeframe": "Cube frame",
    "steppedbipyramid": "Stepped bipyramid",
    "triangle": "Triangle of triangles",
    "hexhex": "Hexagon of hexagons",
}

# mode -> label. Periodic modes take the tiling's label; the flat triangle
# grid keeps its own historical CLI label.
MODE_LABELS = {
    **{t.mode(s): t.label
       for t in TILING_SPECS for s in SURFACE_SPECS if t.allows(s)},
    "trigrid": "Triangle grid",
    **SOLO_LABELS,
}

_SOLID_MODES = frozenset(GROUPS["sphere"][1]) | frozenset(GROUPS["polyhedra"][1])
MODES_3D = frozenset(
    _SOLID_MODES
    | {t.mode(s) for t in TILING_SPECS for s in SURFACE_SPECS
       if s.is_3d and t.allows(s)}
)
