from __future__ import annotations

import math

from minesweeper.boards.core import Board3D, LatticePoint, ROOT3, Vec3, _HEX_VERTEX_OFFSETS, _orient_outward, _shared_vertex_adjacency
from minesweeper.boards.tilings import _arch_template, _triangle_vertices




def _torus_position(i: float, j: float, ring: int, tube: int, tube_radius: float) -> Vec3:
    theta = 2 * math.pi * i / ring
    phi = 2 * math.pi * j / tube
    radial = 1.0 + tube_radius * math.cos(phi)
    return (
        radial * math.cos(theta),
        radial * math.sin(theta),
        tube_radius * math.sin(phi),
    )


def torus_board(
    ring: int, tube: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled with ``ring * tube`` quadrilaterals. The grid wraps
    in both directions, so every cell has exactly 8 neighbors."""
    positions = {
        (i, j): _torus_position(i, j, ring, tube, tube_radius)
        for i in range(ring)
        for j in range(tube)
    }
    cells = {
        (i, j): [
            (i, j),
            ((i + 1) % ring, j),
            ((i + 1) % ring, (j + 1) % tube),
            (i, (j + 1) % tube),
        ]
        for i in range(ring)
        for j in range(tube)
    }
    return _torus_oriented(
        "torus", positions, cells, mine_count, radius=1.0 + tube_radius
    )


def _torus_oriented(mode, positions, cells, mine_count, radius) -> Board3D:
    """Assemble a torus board, orienting each polygon outward (away from
    the ring circle through the tube center)."""
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {}
    for cell, keys in cells.items():
        polygon = [positions[key] for key in keys]
        centroid = tuple(sum(c) / len(polygon) for c in zip(*polygon))
        ring_scale = math.hypot(centroid[0], centroid[1])
        ring_point = (centroid[0] / ring_scale, centroid[1] / ring_scale, 0.0)
        outward = tuple(c - p for c, p in zip(centroid, ring_point))
        polygons[cell] = _orient_outward(polygon, outward)
    return Board3D(mode, polygons, adjacency, mine_count, radius=radius)


def torus_triangle_board(
    ring: int, tube: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled with triangles: each quad of the torus grid is
    split along a diagonal, giving ``2 * ring * tube`` cells."""
    positions = {
        (i, j): _torus_position(i, j, ring, tube, tube_radius)
        for i in range(ring)
        for j in range(tube)
    }
    cells = {}
    for i in range(ring):
        for j in range(tube):
            a = (i, j)
            b = ((i + 1) % ring, j)
            c = ((i + 1) % ring, (j + 1) % tube)
            d = (i, (j + 1) % tube)
            cells[(i, j, 0)] = [a, b, c]
            cells[(i, j, 1)] = [a, c, d]
    return _torus_oriented(
        "torustri", positions, cells, mine_count, radius=1.0 + tube_radius
    )


def torus_hex_board(
    rows: int, cols: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """A donut tiled entirely with hexagons (possible because the torus
    has Euler characteristic 0). The hex lattice wraps around the tube
    (``rows``, must be even) and around the ring (``cols``); every cell
    has exactly 6 neighbors."""
    if rows % 2:
        raise ValueError("rows must be even so the offset lattice wraps")
    kx_period, ky_period = 2 * cols, 3 * rows

    def position(kx: int, ky: int) -> Vec3:
        theta = 2 * math.pi * kx / kx_period  # around the ring
        phi = 2 * math.pi * ky / ky_period  # around the tube
        radial = 1.0 + tube_radius * math.cos(phi)
        return (
            radial * math.cos(theta),
            radial * math.sin(theta),
            tube_radius * math.sin(phi),
        )

    cells = {}
    positions = {}
    for r in range(rows):
        for c in range(cols):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            keys = [
                ((kx + ox) % kx_period, (ky + oy) % ky_period)
                for ox, oy in _HEX_VERTEX_OFFSETS
            ]
            cells[(r, c)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    return _torus_oriented(
        "torushex", positions, cells, mine_count, radius=1.0 + tube_radius
    )


def mobius_board(ring: int, width_cells: int, mine_count: int) -> Board3D:
    """A Möbius strip tiled with quadrilaterals: ``ring`` segments
    around, ``width_cells`` across. After a full loop the strip flips,
    so column ``ring`` glues to column 0 upside down."""
    half_width = min(0.7, math.pi * width_cells / ring / 2)

    def vertex_key(i: int, j: int) -> LatticePoint:
        if i >= ring:  # the seam: glue to the start, flipped
            return (i - ring, width_cells - j)
        return (i, j)

    def position(i: int, j: int) -> Vec3:
        u = 2 * math.pi * i / ring
        v = half_width * (2 * j / width_cells - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (
            radial * math.cos(u),
            radial * math.sin(u),
            v * math.sin(u / 2),
        )

    positions = {
        (i, j): position(i, j)
        for i in range(ring)
        for j in range(width_cells + 1)
    }
    cells = {
        (i, j): [
            vertex_key(i, j),
            vertex_key(i + 1, j),
            vertex_key(i + 1, j + 1),
            vertex_key(i, j + 1),
        ]
        for i in range(ring)
        for j in range(width_cells)
    }
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "mobius",
        polygons,
        adjacency,
        mine_count,
        radius=1.0 + half_width,
        two_sided=True,  # non-orientable: no consistent outside
    )


def mobius_triangle_board(ring: int, width_cells: int, mine_count: int) -> Board3D:
    """A Möbius strip tiled with triangles: each quad of the strip is
    split along a diagonal, giving ``2 * ring * width_cells`` cells."""
    half_width = min(0.7, math.pi * width_cells / ring / 2)

    def vertex_key(i: int, j: int):
        if i >= ring:
            return (i - ring, width_cells - j)
        return (i, j)

    def position(i: int, j: int) -> Vec3:
        u = 2 * math.pi * i / ring
        v = half_width * (2 * j / width_cells - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (radial * math.cos(u), radial * math.sin(u), v * math.sin(u / 2))

    positions = {
        (i, j): position(i, j)
        for i in range(ring)
        for j in range(width_cells + 1)
    }
    cells = {}
    for i in range(ring):
        for j in range(width_cells):
            a = vertex_key(i, j)
            b = vertex_key(i + 1, j)
            c = vertex_key(i + 1, j + 1)
            d = vertex_key(i, j + 1)
            cells[(i, j, 0)] = [a, b, c]
            cells[(i, j, 1)] = [a, c, d]
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "mobiustri", polygons, adjacency, mine_count,
        radius=1.0 + half_width, two_sided=True,
    )


def mobius_hex_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """A Möbius strip tiled with hexagons: ``ring`` columns of ``rows``
    hexagons glued end-to-start with a vertical flip. ``rows`` must be
    odd so the offset lattice maps onto itself under the flip."""
    if rows % 2 == 0:
        raise ValueError("rows must be odd so the lattice survives the flip")
    kx_period = 2 * ring
    ky_top = 3 * rows + 1  # the flip mirrors ky about the strip center
    half_width = min(0.7, math.pi * rows / ring)

    def canonical(kx: int, ky: int):
        if kx >= kx_period:
            return (kx - kx_period, ky_top - ky)
        return (kx, ky)

    def position(kx: int, ky: int) -> Vec3:
        u = 2 * math.pi * kx / kx_period
        v = half_width * (2 * ky / ky_top - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (radial * math.cos(u), radial * math.sin(u), v * math.sin(u / 2))

    cells = {}
    positions = {}
    for c in range(ring):
        for r in range(rows):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            keys = [canonical(kx + ox, ky + oy) for ox, oy in _HEX_VERTEX_OFFSETS]
            cells[(r, c)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "mobiushex", polygons, adjacency, mine_count,
        radius=1.0 + half_width, two_sided=True,
    )


def cylinder_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """The side surface of a cylinder tiled with quadrilaterals: ``ring``
    segments around, ``rows`` up the axis. Wraps around the ring only;
    the ends are open, so the inside is visible."""
    row_height = 2 * math.pi / ring * 0.9  # near-square tiles
    height = rows * row_height

    def position(i: int, j: int) -> Vec3:
        theta = 2 * math.pi * i / ring
        return (math.cos(theta), j * row_height - height / 2, math.sin(theta))

    positions = {
        (i, j): position(i, j) for i in range(ring) for j in range(rows + 1)
    }
    cells = {
        (i, j): [
            (i, j),
            ((i + 1) % ring, j),
            ((i + 1) % ring, j + 1),
            (i, j + 1),
        ]
        for i in range(ring)
        for j in range(rows)
    }
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "cylinder",
        polygons,
        adjacency,
        mine_count,
        radius=math.hypot(1.0, height / 2),
        two_sided=True,  # open ends: the inner surface is visible
    )


def cylinder_triangle_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """The side of a cylinder tiled with triangles: ``ring`` triangles
    around (must be even so up/down triangles alternate cleanly across
    the seam), ``rows`` up the axis."""
    if ring % 2:
        raise ValueError("ring must be even for the triangle strip to wrap")
    # lattice x unit is half a triangle side; make triangles near-equilateral
    row_height = 2 * math.pi / ring * ROOT3 * 0.9
    height = rows * row_height

    def position(kx: int, ky: int) -> Vec3:
        theta = 2 * math.pi * kx / ring
        return (math.cos(theta), ky * row_height - height / 2, math.sin(theta))

    cells = {}
    positions = {}
    for r in range(rows):
        for i in range(ring):
            keys = [
                (kx % ring, ky)
                for kx, ky in _triangle_vertices(i, r, up=(r + i) % 2 == 0)
            ]
            cells[(r, i)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "cyltri", polygons, adjacency, mine_count,
        radius=math.hypot(1.0, height / 2), two_sided=True,
    )


def cylinder_hex_board(ring: int, rows: int, mine_count: int) -> Board3D:
    """The side of a cylinder tiled with hexagons: ``ring`` columns
    around, ``rows`` up the axis."""
    kx_period = 2 * ring
    # lattice units for regular hexagons: x = sqrt(3)/2 * s, y = s / 2,
    # with the x unit pinned to the arc length around the cylinder
    ky_unit = 2 * math.pi / kx_period / ROOT3
    height = (3 * rows + 1) * ky_unit

    def position(kx: int, ky: int) -> Vec3:
        theta = 2 * math.pi * kx / kx_period
        return (math.cos(theta), ky * ky_unit - height / 2, math.sin(theta))

    cells = {}
    positions = {}
    for r in range(rows):
        for c in range(ring):
            kx = 2 * c + (r % 2) + 1
            ky = 3 * r + 2
            keys = [
                ((kx + ox) % kx_period, ky + oy) for ox, oy in _HEX_VERTEX_OFFSETS
            ]
            cells[(r, c)] = keys
            for key in keys:
                if key not in positions:
                    positions[key] = position(*key)
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        "cylhex", polygons, adjacency, mine_count,
        radius=math.hypot(1.0, height / 2), two_sided=True,
    )


def _arch_cells(template, nx: int, ny: int, tiling: str, wrap_rows: bool = True):
    """All cells of an nx x ny grid of domain copies, vertex keys wrapped
    modulo the grid: key = (domain column, domain row, tag). Rows stay
    unwrapped for open-ended surfaces (cylinder)."""
    cells = {}
    for m in range(nx):
        for n in range(ny):
            for name, refs in template.cells:
                keys = [((m + dm) % nx, (n + dn) % ny if wrap_rows else n + dn, tag)
                        for tag, dm, dn in refs]
                if len(set(keys)) < len(keys):  # a cell met its own wrap
                    raise ValueError(f"{nx}x{ny} is too small for {tiling}")
                cells[(m, n, name)] = keys
    return cells


def arch_torus_board(
    tiling: str, nx: int, ny: int, mine_count: int, tube_radius: float = 0.45
) -> Board3D:
    """An Archimedean tiling wrapped around a donut: ``nx`` domain copies
    around the ring, ``ny`` around the tube."""
    template = _arch_template(tiling)
    ring = nx * template.width
    tube = ny * template.height

    def position(m: int, n: int, tag) -> Vec3:
        vx, vy = template.verts[tag]
        theta = 2 * math.pi * (m * template.width + vx) / ring
        phi = 2 * math.pi * (n * template.height + vy) / tube
        radial = 1.0 + tube_radius * math.cos(phi)
        return (
            radial * math.cos(theta),
            radial * math.sin(theta),
            tube_radius * math.sin(phi),
        )

    cells = _arch_cells(template, nx, ny, tiling)
    positions = {key: position(*key) for keys in cells.values() for key in keys}
    return _torus_oriented(
        "torus" + tiling, positions, cells, mine_count, radius=1.0 + tube_radius
    )


def _assemble_two_sided(mode, cells, positions, mine_count, radius) -> Board3D:
    adjacency = _shared_vertex_adjacency(cells)
    polygons = {
        cell: [positions[key] for key in keys] for cell, keys in cells.items()
    }
    return Board3D(
        mode, polygons, adjacency, mine_count, radius=radius, two_sided=True
    )


def arch_cylinder_board(
    tiling: str, ring: int, rows: float, mine_count: int, cut: float = 0.0
) -> Board3D:
    """An Archimedean tiling around the side of a cylinder: ``ring``
    domain copies around, ``rows`` up the axis, open ends. ``cut``
    shifts where the strip starts within the repeating rows and ``rows``
    may be fractional: along a tiling's horizontal edge-lines these make
    the rims flat. Tilings without such lines (the snubs) get a clean
    but zigzag rim: cells are only ever whole."""
    template = _arch_template(tiling)
    height = template.height
    unit = 2 * math.pi / (ring * template.width)  # arc length of one edge unit
    middle = rows * height / 2 + cut

    def position(m: int, n: int, tag) -> Vec3:
        vx, vy = template.verts[tag]
        theta = (m * template.width + vx) * unit
        return (
            math.cos(theta),
            (n * height + vy - middle) * unit,
            math.sin(theta),
        )

    centroids = {
        name: sum(dn * height + template.verts[tag][1] for tag, _, dn in refs)
        / len(refs)
        for name, refs in template.cells
    }
    cells = {}
    for m in range(ring):
        for n in range(math.ceil(rows) + 1):
            for name, refs in template.cells:
                if not cut - 1e-9 <= centroids[name] + n * height < rows * height + cut - 1e-9:
                    continue  # this row copy of the cell is outside the strip
                keys = [((m + dm) % ring, n + dn, tag) for tag, dm, dn in refs]
                if len(set(keys)) < len(keys):
                    raise ValueError(f"ring {ring} is too small for {tiling}")
                cells[(m, n, name)] = keys
    positions = {key: position(*key) for keys in cells.values() for key in keys}
    return _assemble_two_sided(
        "cyl" + tiling, cells, positions, mine_count,
        radius=max(math.hypot(*p) for p in positions.values()),
    )


def arch_mobius_board(tiling: str, ring: int, rows: int, mine_count: int) -> Board3D:
    """An Archimedean tiling on a Möbius strip: ``ring`` domain copies
    around, ``rows`` across; after a full loop the strip glues to its
    start flipped. The flip needs a horizontal mirror symmetry. p4g
    (snub square) only has a glide — mirror plus half a domain — so its
    ring counts half-domains and must be odd for the seam to close.
    3.3.3.3.6 (snub hexagonal) is chiral: no mirror, no glide, so no
    Möbius strip at all (its mirror image is a different tiling)."""
    template = _arch_template(tiling)
    if template.mirror is None:
        raise ValueError(f"{tiling} is chiral and cannot wrap a Möbius strip")
    if template.glide:
        if ring % 2 == 0:
            raise ValueError("ring counts half-domains and must be odd")
        halves = ring
    else:
        halves = 2 * ring
    width, height = template.width, template.height
    q, odd = divmod(halves, 2)
    length = halves * width / 2
    strip = rows * height
    half_width = min(0.7, math.pi * strip / length / 2)

    def flipped(mi: int, ni: int, tag):
        image, dm, dn = template.mirror[tag]
        return image, mi + dm - odd, rows - 1 - ni + dn

    def canonical(mi: int, ni: int, tag):
        # bring x = mi*width + vx into [0, length), flipping at the seam;
        # measured in half-domains, with slack for the rounded tags
        while 2 * mi + 2 * template.verts[tag][0] / width >= halves - 1e-5:
            tag, mi, ni = flipped(mi - q, ni, tag)
        while 2 * mi + 2 * template.verts[tag][0] / width < -1e-5:
            tag, mi, ni = flipped(mi + q + odd, ni, tag)
        return (mi, ni, tag)

    def position(mi: int, ni: int, tag) -> Vec3:
        vx, vy = template.verts[tag]
        u = 2 * math.pi * (mi * width + vx) / length
        v = half_width * (2 * (ni * height + vy) / strip - 1)
        radial = 1.0 + v * math.cos(u / 2)
        return (radial * math.cos(u), radial * math.sin(u), v * math.sin(u / 2))

    centroids = {
        name: sum(dm * width + template.verts[tag][0] for tag, dm, _ in refs)
        / len(refs)
        for name, refs in template.cells
    }
    cells = {}
    for m in range(q + 1):
        for n in range(rows):
            for name, refs in template.cells:
                if not -1e-9 <= centroids[name] + m * width < length - 1e-9:
                    continue  # this domain copy of the cell is past the seam
                keys = [canonical(m + dm, n + dn, tag) for tag, dm, dn in refs]
                if len(set(keys)) < len(keys):
                    raise ValueError(f"ring {ring} is too small for {tiling}")
                cells[(m, n, name)] = keys
    positions = {key: position(*key) for keys in cells.values() for key in keys}
    return _assemble_two_sided(
        "mobius" + tiling, cells, positions, mine_count,
        radius=max(math.hypot(*p) for p in positions.values()),
    )
