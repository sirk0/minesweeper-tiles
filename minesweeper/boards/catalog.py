from __future__ import annotations



MODE_LABELS = {
    "square": "Squares",
    "triangle": "Triangle of triangles",
    "trigrid": "Triangle grid",
    "hex": "Hexagons",
    "hexhex": "Hexagon of hexagons",
    "penrose": "Penrose rhombi",
    "hat": "The Hat",
    "elongated": "Elongated triangular",
    "snubsquare": "Snub square",
    "kagome": "Kagome",
    "snubhex": "Snub hexagonal",
    "truncsquare": "Truncated square",
    "trunchex": "Truncated hexagonal",
    "rhombitrihex": "Rhombitrihexagonal",
    "trunctrihex": "Truncated trihexagonal",
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
    "torus": "Squares",
    "torustri": "Triangles",
    "torushex": "Hexagons",
    "toruselongated": "Elongated triangular",
    "torussnubsquare": "Snub square",
    "toruskagome": "Kagome",
    "torussnubhex": "Snub hexagonal",
    "torustruncsquare": "Truncated square",
    "torustrunchex": "Truncated hexagonal",
    "torusrhombitrihex": "Rhombitrihexagonal",
    "torustrunctrihex": "Truncated trihexagonal",
    "mobius": "Squares",
    "mobiustri": "Triangles",
    "mobiushex": "Hexagons",
    "mobiuselongated": "Elongated triangular",
    "mobiussnubsquare": "Snub square",
    "mobiuskagome": "Kagome",
    "mobiustruncsquare": "Truncated square",
    "mobiustrunchex": "Truncated hexagonal",
    "mobiusrhombitrihex": "Rhombitrihexagonal",
    "mobiustrunctrihex": "Truncated trihexagonal",
    "cylinder": "Squares",
    "cyltri": "Triangles",
    "cylhex": "Hexagons",
    "cylelongated": "Elongated triangular",
    "cylsnubsquare": "Snub square",
    "cylkagome": "Kagome",
    "cylsnubhex": "Snub hexagonal",
    "cyltruncsquare": "Truncated square",
    "cyltrunchex": "Truncated hexagonal",
    "cylrhombitrihex": "Rhombitrihexagonal",
    "cyltrunctrihex": "Truncated trihexagonal",
}

# The menu picks a group, then a tiling, then — for the periodic
# tilings — a surface. Every periodic tiling wraps every surface, with
# one exception: 3.3.3.3.6 (snub hexagonal) is chiral (p6, no mirror or
# glide), so the orientation-reversing Möbius seam cannot glue it to
# itself; the menu shows that surface disabled. The sphere is its own
# group: none of these periodic patterns can tile it (Euler's formula
# forces curvature in), so it offers spherical tilings instead.

SURFACE_LABELS = {
    "flat": "Flat",
    "torus": "Donut",
    "cylinder": "Cylinder",
    "mobius": "Möbius strip",
}

TILINGS = {  # tiling -> (label, {surface: mode})
    "square": (
        "Squares",
        {"flat": "square", "torus": "torus",
         "cylinder": "cylinder", "mobius": "mobius"},
    ),
    "tri": (
        "Triangles",
        {"flat": "trigrid", "torus": "torustri",
         "cylinder": "cyltri", "mobius": "mobiustri"},
    ),
    "hex": (
        "Hexagons",
        {"flat": "hex", "torus": "torushex",
         "cylinder": "cylhex", "mobius": "mobiushex"},
    ),
    "elongated": (
        "Elongated triangular",
        {"flat": "elongated", "torus": "toruselongated",
         "cylinder": "cylelongated", "mobius": "mobiuselongated"},
    ),
    "snubsquare": (
        "Snub square",
        {"flat": "snubsquare", "torus": "torussnubsquare",
         "cylinder": "cylsnubsquare", "mobius": "mobiussnubsquare"},
    ),
    "kagome": (
        "Kagome",
        {"flat": "kagome", "torus": "toruskagome",
         "cylinder": "cylkagome", "mobius": "mobiuskagome"},
    ),
    "snubhex": (
        "Snub hexagonal",
        {"flat": "snubhex", "torus": "torussnubhex",
         "cylinder": "cylsnubhex"},  # chiral: no Möbius strip
    ),
    "truncsquare": (
        "Truncated square",
        {"flat": "truncsquare", "torus": "torustruncsquare",
         "cylinder": "cyltruncsquare", "mobius": "mobiustruncsquare"},
    ),
    "trunchex": (
        "Truncated hexagonal",
        {"flat": "trunchex", "torus": "torustrunchex",
         "cylinder": "cyltrunchex", "mobius": "mobiustrunchex"},
    ),
    "rhombitrihex": (
        "Rhombitrihexagonal",
        {"flat": "rhombitrihex", "torus": "torusrhombitrihex",
         "cylinder": "cylrhombitrihex", "mobius": "mobiusrhombitrihex"},
    ),
    "trunctrihex": (
        "Truncated trihexagonal",
        {"flat": "trunctrihex", "torus": "torustrunctrihex",
         "cylinder": "cyltrunctrihex", "mobius": "mobiustrunctrihex"},
    ),
}

GROUPS = {  # group -> (label, modes); the periodic group goes via TILINGS
    "periodic": ("Periodic tilings", ()),
    "aperiodic": ("Aperiodic", ("penrose", "hat")),
    "sphere": ("Sphere", ("sphere", "c80", "c180", "spheretri", "snubdodec")),
    "polyhedra": (
        "Polyhedra",
        ("cube", "tetrahedron", "tetraframe", "cubeframe", "steppedbipyramid"),
    ),
    "shaped": ("Shaped boards", ("triangle", "hexhex")),
}

MODES_3D = frozenset(
    {"sphere", "c80", "c180", "spheretri", "snubdodec", "cube", "tetrahedron",
     "tetraframe", "cubeframe", "steppedbipyramid"}
    | {mode for mode in MODE_LABELS if mode.startswith(("torus", "mobius", "cyl"))}
)
