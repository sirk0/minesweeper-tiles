// Port of the data-driven parts of minesweeper/boards/catalog.py, reading the
// same data/catalog.json. M1 needs the flat regular modes; the derivations
// mirror the Python and grow as later milestones port more of the catalog.
import catalog from "@data/catalog.json";

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
export const TILINGS_BY_KEY = new Map(REGULAR_TILINGS.map((t) => [t.key, t]));
export const SOLO_LABELS = catalog.soloLabels as Record<string, string>;
export const MENU = catalog.menu;

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

// mode -> the SurfaceSpec it wraps (only the ported regular tilings for now;
// grows with the Archimedean tilings in M4). Mirrors catalog.py's _MODE_SURFACE.
const MODE_SURFACE = new Map<string, SurfaceSpec>();
for (const tiling of REGULAR_TILINGS) {
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
  for (const t of REGULAR_TILINGS) {
    const flat = t.modeOverrides["flat"] ?? t.key;
    labels[flat] = t.label;
  }
  labels["trigrid"] = "Triangle grid";
  return labels;
})();

// Menu groupings for the 3D one-off boards (M2: Sphere and Other).
export const SPHERE_MODES = MENU.sphereModes as string[];
export const OTHER_MODES = MENU.otherModes as string[];
