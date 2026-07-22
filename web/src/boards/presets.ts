// Port of minesweeper/boards/presets.py's build entry point, reading the same
// data/presets.json. A builder-name → function dispatch mirrors Python's
// _JSON_BUILDERS. M1 ported the flat regular modes; M2 adds the solids.
import presetsData from "@data/presets.json";
import { DIFFICULTIES } from "./catalog";
import type { AnyBoard } from "./core";
import {
  c180Board,
  c80Board,
  cubeBoard,
  cubeFrameBoard,
  snubDodecahedronBoard,
  sphereBoard,
  sphereTriangleBoard,
  steppedBipyramidBoard,
  tetrahedronBoard,
  tetrahedronFrameBoard,
} from "./solids";
import {
  hexBoard,
  hexhexBoard,
  squareBoard,
  triangleBoard,
  triangleGridBoard,
} from "./tilings";

type Builder = (...args: number[]) => AnyBoard;

const BUILDERS: Record<string, Builder> = {
  square_board: squareBoard,
  triangle_board: triangleBoard,
  triangle_grid_board: triangleGridBoard,
  hex_board: hexBoard,
  hexhex_board: hexhexBoard,
  sphere_board: sphereBoard,
  c80_board: c80Board,
  c180_board: c180Board,
  sphere_triangle_board: sphereTriangleBoard,
  snub_dodecahedron_board: snubDodecahedronBoard,
  cube_board: cubeBoard,
  cube_frame_board: cubeFrameBoard,
  tetrahedron_board: tetrahedronBoard,
  tetrahedron_frame_board: tetrahedronFrameBoard,
  stepped_bipyramid_board: steppedBipyramidBoard,
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

export function buildBoard(mode: string, difficulty: string): AnyBoard {
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
