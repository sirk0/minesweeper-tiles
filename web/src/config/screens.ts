// Typed accessor for the shared UI-screen configuration
// (`data/ui/screens.json` at the repo root). The JSON is the single source
// of truth for screen chrome so the Python and TypeScript front-ends stay in
// sync; this module gives the TS app compile-time types over it.
import raw from "@data/ui/screens.json";

export type DifficultyKey = string;

export interface Difficulty {
  key: DifficultyKey;
  label: string;
}

export interface Theme {
  background: string;
  panel: string;
  accent: string;
  text: string;
  muted: string;
  danger: string;
}

export interface HudSlot {
  slot: string;
  kind?: string;
  label?: string;
  icon?: string;
  action?: string;
  toggle?: boolean;
  source?: string;
  digits?: number;
  visibleWhen?: string;
}

export interface Hud {
  left: HudSlot[];
  center: HudSlot[];
  right: HudSlot[];
}

export interface SmileyFaces {
  playing: string;
  won: string;
  lost: string;
  pressed: string;
}

export interface MenuEntry {
  key: string;
  label: string;
  kind: "mode" | "surface" | "group";
  hint?: string;
  mode?: string;
  surface?: string;
  children?: string[];
}

export interface Menu {
  title: string;
  root: MenuEntry[];
}

export interface ScreenConfig {
  version: number;
  theme: Theme;
  difficulties: Difficulty[];
  defaultDifficulty: DifficultyKey;
  hud: Hud;
  smiley: SmileyFaces;
  menu: Menu;
}

export const screens = raw as unknown as ScreenConfig;

export function difficulty(key: DifficultyKey): Difficulty {
  const found = screens.difficulties.find((d) => d.key === key);
  if (!found) throw new Error(`unknown difficulty: ${key}`);
  return found;
}
