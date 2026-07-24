import { screens } from "../config/screens";
import {
  DUAL_ARCH,
  FAMILY_LABELS,
  MENU,
  MODE_LABELS,
  OTHER_MODES,
  SHAPED_MODES,
  SPHERE_MODES,
  SURFACES,
  TILINGS_BY_KEY,
  UNIFORM_ARCH,
  modeFor,
  tilingAllows,
} from "../boards/catalog";
import { MODES } from "../boards/presets";

// Geometry-first menu, mirroring the pygame MenuScreen (gui.py). The home page
// lists Classic, Flat, Flat manifolds, Sphere, Other. Classic launches flat
// squares straight away; Flat and every flat manifold (plane, cylinder, Möbius,
// Klein, torus) open the same tiling picker — the regular tilings directly, the
// Uniform / Dual-uniform / (plane-only) Aperiodic families as submenus, then a
// Random tiling entry. Sphere and Other list their finished boards (Other also
// carries the shaped flat boards). Title, difficulty row and theme come from the
// shared UI-screen config.

export interface MenuSelection {
  mode: string;
  difficulty: string;
}

const ROOT_LABELS = MENU.rootLabels as Record<string, string>;
const MANIFOLD_ORDER = MENU.manifoldOrder as string[];
const MANIFOLD_LABELS = MENU.manifoldLabels as Record<string, string>;

// The regular tilings shown directly in every picker.
const PICKER_REGULAR = MENU.pickerRegular as string[];
// The aperiodic tilings exist on the plane only; the flat picker carries them
// as one more family submenu after the uniform / dual ones (M5).
const APERIODIC = MENU.aperiodic as string[];

interface ModeEntry {
  mode: string;
  label: string;
}

interface Family {
  key: string;
  label: string;
  modes: ModeEntry[];
}

/** The tiling picker for a surface: the regular tilings shown directly, then
 * the uniform and dual families (and, on the plane, aperiodic) that have any
 * built modes on that surface. */
interface Picker {
  direct: ModeEntry[];
  families: Family[];
}

/** Every mode reachable through a surface's picker — the pool the Random entry
 * draws from (mirrors catalog.py picker_modes). */
function pickerModes(picker: Picker): string[] {
  return [
    ...picker.direct.map((e) => e.mode),
    ...picker.families.flatMap((f) => f.modes.map((m) => m.mode)),
  ];
}

/** The one-line description of a surface's picker: the regular tilings shown
 * directly, then each family (uniform / dual / aperiodic) available on it — so
 * the hint reflects everything reachable, not just the three basic tilings. */
function pickerHint(surfaceKey: string): string {
  const picker = pickerFor(surfaceKey);
  return [
    ...picker.direct.map((e) => e.label),
    ...picker.families.map((f) => f.label),
  ].join(" · ");
}

/** The built modes for a set of tiling keys on a surface, in the given order. */
function tilingModes(keys: string[], surfaceKey: string): ModeEntry[] {
  const surface = SURFACES.get(surfaceKey);
  if (!surface) return [];
  const out: ModeEntry[] = [];
  for (const key of keys) {
    const tiling = TILINGS_BY_KEY.get(key);
    if (!tiling || !tilingAllows(tiling, surface)) continue;
    const mode = modeFor(key, surfaceKey);
    if (MODES.includes(mode)) out.push({ mode, label: tiling.label });
  }
  return out;
}

function pickerFor(surfaceKey: string): Picker {
  const direct = tilingModes(PICKER_REGULAR, surfaceKey);
  const families: Family[] = [];
  for (const [key, keys] of [
    ["uniform", UNIFORM_ARCH],
    ["dual", DUAL_ARCH],
  ] as const) {
    const modes = tilingModes(keys, surfaceKey);
    if (modes.length > 0) {
      families.push({ key, label: FAMILY_LABELS[key] ?? key, modes });
    }
  }
  if (surfaceKey === "flat") {
    const modes = APERIODIC.filter((m) => MODES.includes(m)).map((mode) => ({
      mode,
      label: MODE_LABELS[mode] ?? mode,
    }));
    if (modes.length > 0) {
      families.push({ key: "aperiodic", label: FAMILY_LABELS["aperiodic"] ?? "Aperiodic", modes });
    }
  }
  return { direct, families };
}

interface SurfaceEntry {
  key: string;
  label: string;
}

interface PickerGroup {
  key: string;
  label: string;
  kind: "picker";
  surfaceKey: string;
}

interface ManifoldGroup {
  key: string;
  label: string;
  kind: "manifolds";
  surfaces: SurfaceEntry[];
}

interface ModeGroup {
  key: string;
  label: string;
  kind: "modes";
  modes: string[];
}

type Group = PickerGroup | ManifoldGroup | ModeGroup;

export class Menu {
  readonly root: HTMLElement;
  private difficulty = screens.defaultDifficulty;
  private readonly groups: Group[];
  private readonly body: HTMLElement;

  constructor(private readonly onSelect: (sel: MenuSelection) => void) {
    const groups: Group[] = [
      { key: "flat", label: ROOT_LABELS["flat"] ?? "Flat", kind: "picker", surfaceKey: "flat" },
      {
        key: "manifolds",
        label: ROOT_LABELS["manifolds"] ?? "Flat manifolds",
        kind: "manifolds",
        surfaces: this.manifoldSurfaces(),
      },
      { key: "sphere", label: ROOT_LABELS["sphere"] ?? "Sphere", kind: "modes", modes: [...SPHERE_MODES] },
      // Other: the solids and, at the end, the shaped flat boards (triangle of
      // triangles, hexagon of hexagons) — matching Python's OTHER_MODES + SHAPED_MODES.
      {
        key: "other",
        label: ROOT_LABELS["other"] ?? "Other",
        kind: "modes",
        modes: [...OTHER_MODES, ...SHAPED_MODES],
      },
    ];
    this.groups = groups.filter((g) => {
      if (g.kind === "modes") return (g.modes = g.modes.filter((m) => MODES.includes(m))).length > 0;
      if (g.kind === "manifolds") return g.surfaces.length > 0;
      const picker = pickerFor(g.surfaceKey);
      return picker.direct.length + picker.families.length > 0;
    });

    this.root = document.createElement("section");
    this.root.className = "menu";

    const title = document.createElement("h1");
    title.className = "menu-title";
    title.textContent = screens.menu.title;

    this.body = document.createElement("div");
    this.body.className = "menu-body";

    this.root.append(title, this.body, this.difficultyRow());
    this.showRoot();
  }

  show(): void {
    this.root.hidden = false;
    this.showRoot();
  }
  hide(): void {
    this.root.hidden = true;
  }

  private showRoot(): void {
    const list = document.createElement("ul");
    list.className = "menu-list";
    // Classic — flat squares, launched straight away (gui.py MenuScreen).
    if (MODES.includes("square")) {
      list.append(
        this.launchRow("square", ROOT_LABELS["classic"] ?? "Classic", "Flat squares — the original."),
      );
    }
    for (const group of this.groups) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.className = "menu-entry";
      btn.dataset.group = group.key;
      const label = document.createElement("span");
      label.className = "menu-entry-label";
      label.textContent = group.label;
      const hint = document.createElement("span");
      hint.className = "menu-entry-hint";
      hint.textContent = this.groupHint(group);
      btn.append(label, hint);
      btn.addEventListener("click", () => this.showGroup(group));
      li.append(btn);
      list.append(li);
    }
    this.body.replaceChildren(list);
  }

  private groupHint(group: Group): string {
    if (group.kind === "modes") return group.modes.map((m) => MODE_LABELS[m] ?? m).join(" · ");
    if (group.kind === "manifolds") return group.surfaces.map((s) => s.label).join(" · ");
    return pickerHint(group.surfaceKey);
  }

  private showGroup(group: Group): void {
    if (group.kind === "picker") {
      this.showPicker(group.label, group.surfaceKey, () => this.showRoot());
      return;
    }
    const back = this.backRow(group.label, () => this.showRoot());
    const list = document.createElement("ul");
    list.className = "menu-list";
    if (group.kind === "modes") {
      for (const mode of group.modes) list.append(this.entryRow(mode, MODE_LABELS[mode] ?? mode));
    } else {
      for (const surface of group.surfaces) list.append(this.surfaceRow(group, surface));
    }
    this.body.replaceChildren(back, list);
  }

  /** The shared tiling picker for a surface (the plane or a flat manifold):
   * regular tilings directly, then the uniform / dual (and, on the plane,
   * aperiodic) families as submenus, then a Random tiling entry. */
  private showPicker(label: string, surfaceKey: string, onBack: () => void): void {
    const picker = pickerFor(surfaceKey);
    const back = this.backRow(label, onBack);
    const list = document.createElement("ul");
    list.className = "menu-list";
    for (const entry of picker.direct) list.append(this.entryRow(entry.mode, entry.label));
    for (const family of picker.families) {
      list.append(
        this.submenuRow(family.label, () =>
          this.showFamily(family, () => this.showPicker(label, surfaceKey, onBack)),
        ),
      );
    }
    const pool = pickerModes(picker);
    if (pool.length > 0) list.append(this.randomRow(pool));
    this.body.replaceChildren(back, list);
  }

  private showFamily(family: Family, onBack: () => void): void {
    const back = this.backRow(family.label, onBack);
    const list = document.createElement("ul");
    list.className = "menu-list";
    for (const entry of family.modes) list.append(this.entryRow(entry.mode, entry.label));
    this.body.replaceChildren(back, list);
  }

  private showSurface(group: ManifoldGroup, surface: SurfaceEntry): void {
    this.showPicker(surface.label, surface.key, () => this.showGroup(group));
  }

  /** The surfaces that have any built tiling, in the shared manifold order.
   * Matches Python's MANIFOLD_ORDER, which includes the plane ("Plane") ahead
   * of the wrapped surfaces. */
  private manifoldSurfaces(): SurfaceEntry[] {
    const entries: SurfaceEntry[] = [];
    for (const key of MANIFOLD_ORDER) {
      const surface = SURFACES.get(key);
      if (!surface) continue;
      const picker = pickerFor(key);
      if (picker.direct.length + picker.families.length > 0) {
        entries.push({ key, label: MANIFOLD_LABELS[key] ?? surface.label });
      }
    }
    return entries;
  }

  private backRow(label: string, onClick: () => void): HTMLElement {
    const back = document.createElement("button");
    back.className = "menu-entry menu-back";
    back.dataset.action = "back";
    const backLabel = document.createElement("span");
    backLabel.className = "menu-entry-label";
    backLabel.textContent = `‹ ${label}`;
    back.append(backLabel);
    back.addEventListener("click", onClick);
    return back;
  }

  private surfaceRow(group: ManifoldGroup, surface: SurfaceEntry): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.surface = surface.key;
    const label = document.createElement("span");
    label.className = "menu-entry-label";
    label.textContent = surface.label;
    const hint = document.createElement("span");
    hint.className = "menu-entry-hint";
    hint.textContent = pickerHint(surface.key);
    btn.append(label, hint);
    btn.addEventListener("click", () => this.showSurface(group, surface));
    li.append(btn);
    return li;
  }

  private submenuRow(label: string, onClick: () => void): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    // menu-submenu lays the label and the › chevron out on one row.
    btn.className = "menu-entry menu-submenu";
    btn.dataset.submenu = label;
    const span = document.createElement("span");
    span.className = "menu-entry-label";
    span.textContent = label;
    const chevron = document.createElement("span");
    chevron.className = "menu-entry-chevron";
    chevron.textContent = "›";
    btn.append(span, chevron);
    btn.addEventListener("click", onClick);
    li.append(btn);
    return li;
  }

  private entryRow(mode: string, label: string): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.mode = mode;
    const span = document.createElement("span");
    span.className = "menu-entry-label";
    span.textContent = label;
    btn.append(span);
    btn.addEventListener("click", () =>
      this.onSelect({ mode, difficulty: this.difficulty }),
    );
    li.append(btn);
    return li;
  }

  /** A root launch entry with a hint (e.g. Classic) — launches its mode on
   * click like entryRow, but shows a subtitle like a group row. */
  private launchRow(mode: string, label: string, hint: string): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.mode = mode;
    const span = document.createElement("span");
    span.className = "menu-entry-label";
    span.textContent = label;
    const hintEl = document.createElement("span");
    hintEl.className = "menu-entry-hint";
    hintEl.textContent = hint;
    btn.append(span, hintEl);
    btn.addEventListener("click", () =>
      this.onSelect({ mode, difficulty: this.difficulty }),
    );
    li.append(btn);
    return li;
  }

  /** The "Random tiling" picker entry — resolves to a random mode from the
   * surface's picker pool at click time (mirrors gui.py's random choice). */
  private randomRow(pool: string[]): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.random = "tiling";
    const span = document.createElement("span");
    span.className = "menu-entry-label";
    span.textContent = "Random tiling";
    btn.append(span);
    btn.addEventListener("click", () => {
      const mode = pool[Math.floor(Math.random() * pool.length)];
      if (mode) this.onSelect({ mode, difficulty: this.difficulty });
    });
    li.append(btn);
    return li;
  }

  private difficultyRow(): HTMLElement {
    const row = document.createElement("div");
    row.className = "menu-difficulty";
    for (const d of screens.difficulties) {
      const btn = document.createElement("button");
      btn.className = "difficulty-btn";
      btn.dataset.key = d.key;
      btn.textContent = d.label;
      btn.classList.toggle("active", d.key === this.difficulty);
      btn.addEventListener("click", () => {
        this.difficulty = d.key;
        for (const b of row.querySelectorAll(".difficulty-btn")) {
          b.classList.toggle("active", (b as HTMLElement).dataset.key === d.key);
        }
      });
      row.append(btn);
    }
    return row;
  }
}
