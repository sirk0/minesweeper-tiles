import { screens, type HudSlot } from "../config/screens";

// The game header, rendered from the shared UI-screen config
// (`data/ui/screens.json`) rather than hand-laid-out, so the pygame and TS
// front-ends can share one description of the chrome. M0 renders the header
// statically; wiring the actions to a live game session lands in M1.

// Inline SVGs for slots whose config declares an `icon` we can draw; slots
// with no entry here fall back to their text label. The flag mirrors the
// in-game glyph (glyphAtlas.ts drawFlag): dark pole and base, red pennant.
const ICONS: Record<string, string> = {
  flag: `<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
    <path d="M10.2 5.8 V18.6" stroke="#202020" stroke-width="1.7" fill="none"/>
    <rect x="7.2" y="18.2" width="9.7" height="1.8" fill="#202020"/>
    <path d="M10.2 5.8 L16.4 8.9 L10.2 12 Z" fill="#e5534b"/>
  </svg>`,
};

export interface HudState {
  minesRemaining: number;
  elapsedSeconds: number;
  status: "playing" | "won" | "lost";
  flagMode: boolean;
  hasCellCycle: boolean;
}

export class Hud {
  readonly root: HTMLElement;
  private state: HudState = {
    minesRemaining: 0,
    elapsedSeconds: 0,
    status: "playing",
    flagMode: false,
    hasCellCycle: false,
  };
  private readonly counters = new Map<string, HTMLElement>();
  private smiley: HTMLButtonElement | null = null;
  private flagBtn: HTMLButtonElement | null = null;

  constructor(private readonly onAction: (action: string) => void) {
    this.root = document.createElement("header");
    this.root.className = "hud";
    const cfg = screens.hud;
    this.root.append(
      this.cluster("hud-left", cfg.left),
      this.cluster("hud-center", cfg.center),
      this.cluster("hud-right", cfg.right),
    );
    this.render();
  }

  setState(next: Partial<HudState>): void {
    this.state = { ...this.state, ...next };
    this.render();
  }

  private cluster(cls: string, slots: HudSlot[]): HTMLElement {
    const el = document.createElement("div");
    el.className = `hud-cluster ${cls}`;
    for (const slot of slots) el.append(this.buildSlot(slot));
    return el;
  }

  private buildSlot(slot: HudSlot): HTMLElement {
    if (slot.kind === "counter") {
      const el = document.createElement("div");
      el.className = "hud-counter";
      el.dataset.slot = slot.slot;
      el.dataset.digits = String(slot.digits ?? 3);
      if (slot.source) this.counters.set(slot.source, el);
      return el;
    }
    if (slot.kind === "reset") {
      const btn = document.createElement("button");
      btn.className = "hud-smiley";
      btn.dataset.slot = slot.slot;
      btn.setAttribute("aria-label", "Restart");
      btn.addEventListener("click", () => this.onAction(slot.action ?? "restart"));
      this.smiley = btn;
      return btn;
    }
    const btn = document.createElement("button");
    btn.className = "hud-btn";
    btn.dataset.slot = slot.slot;
    const icon = slot.icon ? ICONS[slot.icon] : undefined;
    if (icon) {
      btn.classList.add("hud-icon-btn");
      btn.innerHTML = icon;
      btn.setAttribute("aria-label", slot.label ?? slot.slot);
      btn.title = slot.label ?? slot.slot;
    } else {
      btn.textContent = slot.label ?? slot.slot;
    }
    if (slot.action) btn.addEventListener("click", () => this.onAction(slot.action!));
    if (slot.slot === "flag-mode") this.flagBtn = btn;
    if (slot.visibleWhen) btn.dataset.visibleWhen = slot.visibleWhen;
    return btn;
  }

  private render(): void {
    const pad = (n: number, d: number) =>
      Math.max(0, Math.min(10 ** d - 1, Math.floor(n)))
        .toString()
        .padStart(d, "0");
    for (const [source, el] of this.counters) {
      const digits = Number(el.dataset.digits ?? 3);
      const value = source === "minesRemaining" ? this.state.minesRemaining : this.state.elapsedSeconds;
      el.textContent = pad(value, digits);
    }
    if (this.smiley) this.smiley.textContent = screens.smiley[this.state.status];
    if (this.flagBtn) this.flagBtn.classList.toggle("active", this.state.flagMode);
    // Toggle config-driven conditional visibility (e.g. Klein scroll arrows).
    for (const btn of this.root.querySelectorAll<HTMLElement>("[data-visible-when]")) {
      const cond = btn.dataset.visibleWhen;
      const visible = cond === "hasCellCycle" ? this.state.hasCellCycle : true;
      btn.style.display = visible ? "" : "none";
    }
  }
}
