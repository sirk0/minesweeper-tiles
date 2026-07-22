import { screens } from "../config/screens";
import { MENU, MODE_LABELS, OTHER_MODES, SPHERE_MODES } from "../boards/catalog";
import { MODES } from "../boards/presets";

// Minimal menu: the ported modes in labelled groups (flat boards, then the
// Sphere and Other solids per the shared catalog's menu taxonomy). Title,
// difficulty row and theme still come from the shared UI-screen config
// (data/ui/screens.json). The full geometry-first drill-down returns as the
// surface wraps and tiling families are ported.

export interface MenuSelection {
  mode: string;
  difficulty: string;
}

// Present the ported flat modes in a friendly order with their catalog labels.
const FLAT_ORDER = ["square", "trigrid", "hex", "triangle", "hexhex"];

const ROOT_LABELS = MENU.rootLabels as Record<string, string>;

export class Menu {
  readonly root: HTMLElement;
  private difficulty = screens.defaultDifficulty;

  constructor(private readonly onSelect: (sel: MenuSelection) => void) {
    this.root = document.createElement("section");
    this.root.className = "menu";

    const title = document.createElement("h1");
    title.className = "menu-title";
    title.textContent = screens.menu.title;
    this.root.append(title);

    const groups: [string, string[]][] = [
      ["Flat boards", this.orderedFlatModes()],
      [ROOT_LABELS["sphere"] ?? "Sphere", SPHERE_MODES],
      [ROOT_LABELS["other"] ?? "Other", OTHER_MODES],
    ];
    for (const [label, modes] of groups) {
      const ported = modes.filter((m) => MODES.includes(m));
      if (!ported.length) continue;
      const subtitle = document.createElement("p");
      subtitle.className = "menu-subtitle";
      subtitle.textContent = label;
      const list = document.createElement("ul");
      list.className = "menu-list";
      for (const mode of ported) list.append(this.entryRow(mode));
      this.root.append(subtitle, list);
    }

    this.root.append(this.difficultyRow());
  }

  show(): void {
    this.root.hidden = false;
  }
  hide(): void {
    this.root.hidden = true;
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
