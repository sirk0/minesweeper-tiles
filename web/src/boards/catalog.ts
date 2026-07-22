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
