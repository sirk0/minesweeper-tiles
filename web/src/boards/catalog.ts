// Port of the data-driven parts of minesweeper/boards/catalog.py, reading the
// same data/catalog.json. M1 needs the flat regular modes; the derivations
// mirror the Python and grow as later milestones port more of the catalog.
import catalog from "@data/catalog.json";
import { ARCH_TILINGS, archTemplate } from "./tilings";

export interface SurfaceSpec {
  key: string;
  label: string;
  prefix: string;
  is3d: boolean;
  needsMirror: boolean;
  boundaryComponents: number | null;
  tilt: number | null;
  tilings: string[] | null;
}

export interface TilingSpec {
  key: string;
  label: string;
  chiral: boolean;
  modeOverrides: Record<string, string>;
}

export const DIFFICULTIES = catalog.difficulties as string[];
export const SURFACE_SPECS = catalog.surfaces as SurfaceSpec[];
export const SURFACES = new Map(SURFACE_SPECS.map((s) => [s.key, s]));
export const REGULAR_TILINGS = catalog.regularTilings as TilingSpec[];
export const SOLO_LABELS = catalog.soloLabels as Record<string, string>;
export const MENU = catalog.menu;

// The Archimedean (uniform) tilings and their Laves duals are lifted from the
// tilings.ts ARCH_TILINGS registry — the one place they are declared — exactly
// as catalog.py lifts them from ARCH_TILINGS. A tiling whose fundamental-domain
// template has no mirror is chiral (snub hexagonal, floret pentagonal), which
// gates it out of the orientation-reversing Möbius / Klein surfaces.
export const ARCH_TILING_SPECS: TilingSpec[] = ARCH_TILINGS.map((t) => ({
  key: t.key,
  label: t.label,
  chiral: archTemplate(t.key).mirror === null,
  modeOverrides: {},
}));

// Every periodic tiling as the menu sees it: the three regular tilings first,
// then the uniform and dual-uniform families.
export const TILING_SPECS: TilingSpec[] = [...REGULAR_TILINGS, ...ARCH_TILING_SPECS];
export const TILINGS_BY_KEY = new Map(TILING_SPECS.map((t) => [t.key, t]));

// The uniform / dual-uniform picker families — exactly the vertex-transitive
// ARCH_TILINGS and their (face-transitive) Laves duals.
export const UNIFORM_ARCH = ARCH_TILINGS.filter((t) => t.vertexTransitive).map((t) => t.key);
export const DUAL_ARCH = ARCH_TILINGS.filter((t) => !t.vertexTransitive).map((t) => t.key);
export const FAMILY_LABELS = MENU.familyLabels as Record<string, string>;

/** The mode string for a (tiling, surface) pair — the one naming convention. */
export function modeFor(tilingKey: string, surfaceKey: string): string {
  const tiling = TILINGS_BY_KEY.get(tilingKey);
  const surface = SURFACES.get(surfaceKey);
  if (!tiling || !surface) throw new Error(`unknown ${tilingKey}/${surfaceKey}`);
  return tiling.modeOverrides[surfaceKey] ?? surface.prefix + tiling.key;
}

/** Whether a tiling can wrap a surface (port of TilingSpec.allows): a
 * mirror-needing surface (Möbius/Klein) rejects chiral tilings, and a surface
 * may restrict itself to an explicit tiling allow-list. */
export function tilingAllows(tiling: TilingSpec, surface: SurfaceSpec): boolean {
  if (surface.needsMirror && tiling.chiral) return false;
  if (surface.tilings && !surface.tilings.includes(tiling.key)) return false;
  return true;
}

// mode -> the SurfaceSpec it wraps (regular + Archimedean/Laves tilings across
// every surface they allow). Mirrors catalog.py's _MODE_SURFACE.
const MODE_SURFACE = new Map<string, SurfaceSpec>();
for (const tiling of TILING_SPECS) {
  for (const surface of SURFACE_SPECS) {
    if (tilingAllows(tiling, surface)) {
      MODE_SURFACE.set(modeFor(tiling.key, surface.key), surface);
    }
  }
}

/** The SurfaceSpec a periodic (tiling × surface) mode lives on, or null for a
 * one-off solid/aperiodic/shaped mode. */
export function surfaceOf(mode: string): SurfaceSpec | null {
  return MODE_SURFACE.get(mode) ?? null;
}

/** The initial x-rotation (tilt) for a wrapped mode, or null when the mode is
 * flat or a one-off solid (which set their own view). */
export function viewHint(mode: string): number | null {
  const surface = surfaceOf(mode);
  return surface ? surface.tilt : null;
}

// mode -> label for the ported modes. Regular periodic modes take the
// tiling's label; the flat triangle grid keeps its historical label; the
// one-off boards (shaped flats, solids) take their solo labels.
export const MODE_LABELS: Record<string, string> = (() => {
  const labels: Record<string, string> = { ...SOLO_LABELS };
  for (const t of TILING_SPECS) {
    for (const s of SURFACE_SPECS) {
      if (tilingAllows(t, s)) labels[modeFor(t.key, s.key)] = t.label;
    }
  }
  labels["trigrid"] = "Triangle grid";
  return labels;
})();

// Menu groupings for the 3D one-off boards (M2: Sphere and Other).
export const SPHERE_MODES = MENU.sphereModes as string[];
export const OTHER_MODES = MENU.otherModes as string[];
// The shaped flat boards (triangle of triangles, hexagon of hexagons). Python
// lists them at the end of the Other page (catalog.py OTHER_MODES + SHAPED_MODES).
export const SHAPED_MODES = MENU.shapedModes as string[];
