import { screens, type MenuEntry } from "../config/screens";

// A minimal menu shell rendered from the shared UI-screen config. M0 ships the
// home page (title, top-level groups, difficulty row) as a config-driven shell;
// the full drill-down (group → tiling → surface) and mode launching arrive in
// M1 once boards are ported.

export interface MenuSelection {
  entry: MenuEntry;
  difficulty: string;
}

export class Menu {
  readonly root: HTMLElement;
  private difficulty = screens.defaultDifficulty;

  constructor(private readonly onSelect: (sel: MenuSelection) => void) {
    this.root = document.createElement("section");
    this.root.className = "menu";
    this.root.hidden = true;

    const title = document.createElement("h1");
    title.className = "menu-title";
    title.textContent = screens.menu.title;

    const list = document.createElement("ul");
    list.className = "menu-list";
    for (const entry of screens.menu.root) list.append(this.entryRow(entry));

    this.root.append(title, list, this.difficultyRow());
  }

  show(): void {
    this.root.hidden = false;
  }
  hide(): void {
    this.root.hidden = true;
  }

  private entryRow(entry: MenuEntry): HTMLElement {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "menu-entry";
    btn.dataset.key = entry.key;
    const label = document.createElement("span");
    label.className = "menu-entry-label";
    label.textContent = entry.label;
    btn.append(label);
    if (entry.hint) {
      const hint = document.createElement("span");
      hint.className = "menu-entry-hint";
      hint.textContent = entry.hint;
      btn.append(hint);
    }
    btn.addEventListener("click", () =>
      this.onSelect({ entry, difficulty: this.difficulty }),
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
