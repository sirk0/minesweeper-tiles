import { screens } from "../config/screens";
import { MENU, MODE_LABELS, OTHER_MODES, SPHERE_MODES } from "../boards/catalog";
import { MODES } from "../boards/presets";

// Two-level menu: the root screen lists the board groups (flat boards, then
// the Sphere and Other solids per the shared catalog's menu taxonomy);
// picking one shows that group's modes with a back row — so no screen needs
// to scroll. Title, difficulty row and theme still come from the shared
// UI-screen config (data/ui/screens.json). The full geometry-first
// drill-down returns as the surface wraps and tiling families are ported.

export interface MenuSelection {
  mode: string;
  difficulty: string;
}

// Present the ported flat modes in a friendly order with their catalog labels.
const FLAT_ORDER = ["square", "trigrid", "hex", "triangle", "hexhex"];

const ROOT_LABELS = MENU.rootLabels as Record<string, string>;

interface Group {
  key: string;
  label: string;
  modes: string[];
}

export class Menu {
  readonly root: HTMLElement;
  private difficulty = screens.defaultDifficulty;
  private readonly groups: Group[];
  private readonly body: HTMLElement;

  constructor(private readonly onSelect: (sel: MenuSelection) => void) {
    this.groups = [
      { key: "flat", label: "Flat boards", modes: this.orderedFlatModes() },
      { key: "sphere", label: ROOT_LABELS["sphere"] ?? "Sphere", modes: SPHERE_MODES },
      { key: "other", label: ROOT_LABELS["other"] ?? "Other", modes: OTHER_MODES },
    ]
      .map((g) => ({ ...g, modes: g.modes.filter((m) => MODES.includes(m)) }))
      .filter((g) => g.modes.length > 0);

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
      hint.textContent = group.modes.map((m) => MODE_LABELS[m] ?? m).join(" · ");
      btn.append(label, hint);
      btn.addEventListener("click", () => this.showGroup(group));
      li.append(btn);
      list.append(li);
    }
    this.body.replaceChildren(list);
  }

  private showGroup(group: Group): void {
    const back = document.createElement("button");
    back.className = "menu-entry menu-back";
    back.dataset.action = "back";
    const backLabel = document.createElement("span");
    backLabel.className = "menu-entry-label";
    backLabel.textContent = `‹ ${group.label}`;
    back.append(backLabel);
    back.addEventListener("click", () => this.showRoot());

    const list = document.createElement("ul");
    list.className = "menu-list";
    for (const mode of group.modes) list.append(this.entryRow(mode));
    this.body.replaceChildren(back, list);
  }

  private orderedFlatModes(): string[] {
    const solids = new Set([...SPHERE_MODES, ...OTHER_MODES]);
    const known = FLAT_ORDER.filter((m) => MODES.includes(m));
    const rest = MODES.filter((m) => !known.includes(m) && !solids.has(m));
    return [...known, ...rest];
  }

  private entryRow(mode: string): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.mode = mode;
    const label = document.createElement("span");
    label.className = "menu-entry-label";
    label.textContent = MODE_LABELS[mode] ?? mode;
    btn.append(label);
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
