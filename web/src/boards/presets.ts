// Port of minesweeper/boards/presets.py's build entry point, reading the same
// data/presets.json. A builder-name → function dispatch mirrors Python's
// _FLAT_BUILDERS. Only the ported (flat regular) modes are present in M1.
import presetsData from "@data/presets.json";
import { DIFFICULTIES } from "./catalog";
import type { Board } from "./core";
import {
  hexBoard,
  hexhexBoard,
  squareBoard,
  triangleBoard,
  triangleGridBoard,
} from "./tilings";

type Builder = (...args: number[]) => Board;

const BUILDERS: Record<string, Builder> = {
  square_board: squareBoard,
  triangle_board: triangleBoard,
  triangle_grid_board: triangleGridBoard,
  hex_board: hexBoard,
  hexhex_board: hexhexBoard,
};

interface PresetSpec {
  builder: string;
  args: Record<string, number[]>;
}

const PRESETS = presetsData.presets as Record<string, PresetSpec>;

export const MODES: string[] = Object.keys(PRESETS);

export function hasMode(mode: string): boolean {
  return mode in PRESETS;
}

export function buildBoard(mode: string, difficulty: string): Board {
  const spec = PRESETS[mode];
  if (!spec) throw new Error(`unknown mode ${mode}`);
  if (!DIFFICULTIES.includes(difficulty)) {
    throw new Error(`unknown difficulty ${difficulty}`);
  }
  const builder = BUILDERS[spec.builder];
  const args = spec.args[difficulty];
  if (!builder || !args) throw new Error(`no preset for ${mode}/${difficulty}`);
  return builder(...args);
}
