import { screens } from "../config/screens";
import { MODE_LABELS } from "../boards/catalog";
import { MODES } from "../boards/presets";

// M1 minimal menu: launches the ported flat regular boards. Title, difficulty
// row and theme still come from the shared UI-screen config
// (data/ui/screens.json); the mode list comes from the ported board catalog.
// The full geometry-first drill-down returns as more modes are ported.

export interface MenuSelection {
  mode: string;
  difficulty: string;
}

// Present the ported modes in a friendly order with their catalog labels.
const MODE_ORDER = ["square", "trigrid", "hex", "triangle", "hexhex"];

export class Menu {
  readonly root: HTMLElement;
  private difficulty = screens.defaultDifficulty;

  constructor(private readonly onSelect: (sel: MenuSelection) => void) {
    this.root = document.createElement("section");
    this.root.className = "menu";

    const title = document.createElement("h1");
    title.className = "menu-title";
    title.textContent = screens.menu.title;

    const subtitle = document.createElement("p");
    subtitle.className = "menu-subtitle";
    subtitle.textContent = "Flat boards";

    const list = document.createElement("ul");
    list.className = "menu-list";
    for (const mode of this.orderedModes()) list.append(this.entryRow(mode));

    this.root.append(title, subtitle, list, this.difficultyRow());
  }

  show(): void {
    this.root.hidden = false;
  }
  hide(): void {
    this.root.hidden = true;
  }

  private orderedModes(): string[] {
    const known = MODE_ORDER.filter((m) => MODES.includes(m));
    const rest = MODES.filter((m) => !known.includes(m));
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
