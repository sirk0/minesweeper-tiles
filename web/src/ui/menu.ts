import { screens } from "../config/screens";
import {
  DUAL_ARCH,
  FAMILY_LABELS,
  MENU,
  MODE_LABELS,
  OTHER_MODES,
  SPHERE_MODES,
  SURFACES,
  TILINGS_BY_KEY,
  UNIFORM_ARCH,
  modeFor,
  tilingAllows,
} from "../boards/catalog";
import { MODES } from "../boards/presets";

// Geometry-first menu. The root lists the board groups; the flat boards and
// solids drill straight to their modes, while "Flat manifolds" drills one level
// deeper — surface (cylinder / Möbius / Klein / torus) then tiling. Both the
// plane and every flat manifold open the same tiling picker: the regular
// tilings directly, then the Uniform and Dual-uniform families as submenus
// (M4). Title, difficulty row and theme come from the shared UI-screen config.

export interface MenuSelection {
  mode: string;
  difficulty: string;
}

const ROOT_LABELS = MENU.rootLabels as Record<string, string>;
const MANIFOLD_ORDER = MENU.manifoldOrder as string[];
const MANIFOLD_LABELS = MENU.manifoldLabels as Record<string, string>;

// The regular tilings shown directly in the picker, then the one-off shaped
// flat boards that only exist on the plane (triangle-of-triangles, hexhex).
const PICKER_REGULAR = ["square", "tri", "hex"];
const FLAT_SHAPED = ["triangle", "hexhex"];
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

/** The tiling picker for a surface: the regular tilings (plus the shaped boards
 * on the plane) shown directly, then the uniform and dual families that have
 * any built modes on that surface. */
interface Picker {
  direct: ModeEntry[];
  families: Family[];
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
  if (surfaceKey === "flat") {
    for (const mode of FLAT_SHAPED) {
      if (MODES.includes(mode)) direct.push({ mode, label: MODE_LABELS[mode] ?? mode });
    }
  }
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
      { key: "flat", label: "Flat boards", kind: "picker", surfaceKey: "flat" },
      {
        key: "manifolds",
        label: ROOT_LABELS["manifolds"] ?? "Flat manifolds",
        kind: "manifolds",
        surfaces: this.manifoldSurfaces(),
      },
      { key: "sphere", label: ROOT_LABELS["sphere"] ?? "Sphere", kind: "modes", modes: [...SPHERE_MODES] },
      { key: "other", label: ROOT_LABELS["other"] ?? "Other", kind: "modes", modes: [...OTHER_MODES] },
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
    return pickerFor(group.surfaceKey).direct.map((e) => e.label).join(" · ");
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
   * regular tilings directly, then the uniform / dual families as submenus. */
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

  /** The 3D wrappable surfaces that have any built tiling, in the shared
   * manifold order. */
  private manifoldSurfaces(): SurfaceEntry[] {
    const entries: SurfaceEntry[] = [];
    for (const key of MANIFOLD_ORDER) {
      const surface = SURFACES.get(key);
      if (!surface || !surface.is3d) continue; // the plane is the Flat group
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
    hint.textContent = pickerFor(surface.key).direct.map((e) => e.label).join(" · ");
    btn.append(label, hint);
    btn.addEventListener("click", () => this.showSurface(group, surface));
    li.append(btn);
    return li;
  }

  private submenuRow(label: string, onClick: () => void): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.submenu = label;
    const span = document.createElement("span");
    span.className = "menu-entry-label";
    span.textContent = label;
    const hint = document.createElement("span");
    hint.className = "menu-entry-hint";
    hint.textContent = "›";
    btn.append(span, hint);
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
