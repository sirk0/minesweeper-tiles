import { screens } from "../config/screens";
import {
  MENU,
  MODE_LABELS,
  OTHER_MODES,
  REGULAR_TILINGS,
  SPHERE_MODES,
  SURFACES,
  modeFor,
  surfaceOf,
  tilingAllows,
} from "../boards/catalog";
import { MODES } from "../boards/presets";

// Geometry-first menu. The root lists the board groups; the flat boards and
// solids drill straight to their modes, while "Flat manifolds" drills one level
// deeper — surface (cylinder / Möbius / Klein / torus) then tiling (squares /
// triangles / hexagons) — so no screen needs to scroll. Title, difficulty row
// and theme come from the shared UI-screen config (data/ui/screens.json). The
// uniform / dual / aperiodic tiling families join as M4 ports the templates.

export interface MenuSelection {
  mode: string;
  difficulty: string;
}

// Present the ported flat modes in a friendly order with their catalog labels.
const FLAT_ORDER = ["square", "trigrid", "hex", "triangle", "hexhex"];

const ROOT_LABELS = MENU.rootLabels as Record<string, string>;
const MANIFOLD_ORDER = MENU.manifoldOrder as string[];
const MANIFOLD_LABELS = MENU.manifoldLabels as Record<string, string>;

interface ModeEntry {
  mode: string;
  label: string;
}

interface SurfaceEntry {
  key: string;
  label: string;
  tilings: ModeEntry[];
}

interface ModeGroup {
  key: string;
  label: string;
  kind: "modes";
  modes: string[];
}

interface SurfaceGroup {
  key: string;
  label: string;
  kind: "surfaces";
  surfaces: SurfaceEntry[];
}

type Group = ModeGroup | SurfaceGroup;

/** A flat mode is one that does not wrap a 3D surface (the plane tilings and
 * the one-off shaped boards). */
function isFlatMode(mode: string): boolean {
  return !surfaceOf(mode)?.is3d;
}

export class Menu {
  readonly root: HTMLElement;
  private difficulty = screens.defaultDifficulty;
  private readonly groups: Group[];
  private readonly body: HTMLElement;

  constructor(private readonly onSelect: (sel: MenuSelection) => void) {
    const groups: Group[] = [
      { key: "flat", label: "Flat boards", kind: "modes", modes: this.orderedFlatModes() },
      {
        key: "manifolds",
        label: ROOT_LABELS["manifolds"] ?? "Flat manifolds",
        kind: "surfaces",
        surfaces: this.manifoldSurfaces(),
      },
      { key: "sphere", label: ROOT_LABELS["sphere"] ?? "Sphere", kind: "modes", modes: [...SPHERE_MODES] },
      { key: "other", label: ROOT_LABELS["other"] ?? "Other", kind: "modes", modes: [...OTHER_MODES] },
    ];
    this.groups = groups.filter((g) =>
      g.kind === "modes"
        ? (g.modes = g.modes.filter((m) => MODES.includes(m))).length > 0
        : g.surfaces.length > 0,
    );

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
    return group.kind === "modes"
      ? group.modes.map((m) => MODE_LABELS[m] ?? m).join(" · ")
      : group.surfaces.map((s) => s.label).join(" · ");
  }

  private showGroup(group: Group): void {
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

  private showSurface(group: SurfaceGroup, surface: SurfaceEntry): void {
    const back = this.backRow(surface.label, () => this.showGroup(group));
    const list = document.createElement("ul");
    list.className = "menu-list";
    for (const t of surface.tilings) list.append(this.entryRow(t.mode, t.label));
    this.body.replaceChildren(back, list);
  }

  private orderedFlatModes(): string[] {
    const known = FLAT_ORDER.filter((m) => MODES.includes(m) && isFlatMode(m));
    const rest = MODES.filter((m) => !known.includes(m) && isFlatMode(m) && !SPHERE_MODES.includes(m) && !OTHER_MODES.includes(m));
    return [...known, ...rest];
  }

  /** The 3D wrappable surfaces, each with the regular tilings it allows that
   * both front-ends build. Derived from the shared catalog (manifold order +
   * regular tilings + chirality gating). */
  private manifoldSurfaces(): SurfaceEntry[] {
    const entries: SurfaceEntry[] = [];
    for (const key of MANIFOLD_ORDER) {
      const surface = SURFACES.get(key);
      if (!surface || !surface.is3d) continue; // the plane is the Flat group
      const tilings: ModeEntry[] = [];
      for (const tiling of REGULAR_TILINGS) {
        if (!tilingAllows(tiling, surface)) continue;
        const mode = modeFor(tiling.key, key);
        if (MODES.includes(mode)) tilings.push({ mode, label: tiling.label });
      }
      if (tilings.length > 0) {
        entries.push({ key, label: MANIFOLD_LABELS[key] ?? surface.label, tilings });
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

  private surfaceRow(group: SurfaceGroup, surface: SurfaceEntry): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.surface = surface.key;
    const label = document.createElement("span");
    label.className = "menu-entry-label";
    label.textContent = surface.label;
    const hint = document.createElement("span");
    hint.className = "menu-entry-hint";
    hint.textContent = surface.tilings.map((t) => t.label).join(" · ");
    btn.append(label, hint);
    btn.addEventListener("click", () => this.showSurface(group, surface));
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
