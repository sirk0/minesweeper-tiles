import { describe, expect, it } from "vitest";
import {
  DUAL_ARCH,
  MENU,
  OTHER_MODES,
  SPHERE_MODES,
  SURFACES,
  TILINGS_BY_KEY,
  UNIFORM_ARCH,
  modeFor,
  tilingAllows,
} from "../../src/boards/catalog";
import { MODES } from "../../src/boards/presets";

// The M4 catalog derivations: the uniform / dual-uniform families lifted from
// the ARCH_TILINGS registry, chirality gating, and the guarantee that every
// built mode is reachable through the geometry-first menu (the picker per
// surface plus the sphere / other groups). Mirrors catalog.py's family split
// and picker_modes reachability.

const PICKER_REGULAR = MENU.pickerRegular as string[];
const FLAT_SHAPED = MENU.shapedModes as string[];
const APERIODIC = MENU.aperiodic as string[];
const MANIFOLD_ORDER = MENU.manifoldOrder as string[];

describe("catalog families", () => {
  it("splits the sixteen template tilings into eight uniform + eight dual", () => {
    expect(UNIFORM_ARCH.length).toBe(8);
    expect(DUAL_ARCH.length).toBe(8);
    expect(new Set([...UNIFORM_ARCH, ...DUAL_ARCH]).size).toBe(16);
  });

  it("marks only the chiral tilings chiral (snub hexagonal + floret)", () => {
    const chiral = [...UNIFORM_ARCH, ...DUAL_ARCH].filter(
      (k) => TILINGS_BY_KEY.get(k)!.chiral,
    );
    expect(new Set(chiral)).toEqual(new Set(["snubhex", "floret"]));
  });

  it("gates chiral tilings out of the mirror-needing surfaces", () => {
    for (const key of ["snubhex", "floret"]) {
      const tiling = TILINGS_BY_KEY.get(key)!;
      expect(tilingAllows(tiling, SURFACES.get("mobius")!)).toBe(false);
      expect(tilingAllows(tiling, SURFACES.get("klein")!)).toBe(false);
      expect(tilingAllows(tiling, SURFACES.get("torus")!)).toBe(true);
    }
  });
});

describe("menu reachability", () => {
  it("reaches every built mode through a group / picker path", () => {
    const reachable = new Set<string>();
    const add = (mode: string): void => {
      if (MODES.includes(mode)) reachable.add(mode);
    };
    for (const surfaceKey of MANIFOLD_ORDER) {
      const surface = SURFACES.get(surfaceKey);
      if (!surface) continue;
      for (const key of [...PICKER_REGULAR, ...UNIFORM_ARCH, ...DUAL_ARCH]) {
        const tiling = TILINGS_BY_KEY.get(key);
        if (tiling && tilingAllows(tiling, surface)) add(modeFor(key, surfaceKey));
      }
      if (surfaceKey === "flat") {
        for (const m of FLAT_SHAPED) add(m);
        for (const m of APERIODIC) add(m); // the flat picker carries the aperiodic tilings
      }
    }
    for (const m of SPHERE_MODES) add(m);
    for (const m of OTHER_MODES) add(m);
    expect(reachable).toEqual(new Set(MODES));
  });
});
