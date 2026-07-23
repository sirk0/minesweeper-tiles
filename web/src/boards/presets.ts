// Port of minesweeper/boards/presets.py's build entry point, reading the same
// data/presets.json. A builder-name → function dispatch mirrors Python's
// _JSON_BUILDERS. M1 ported the flat regular modes; M2 adds the solids.
import presetsData from "@data/presets.json";
import { hatBoard, penroseBoard } from "./aperiodic";
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
  archimedeanBoard,
  hexBoard,
  hexhexBoard,
  squareBoard,
  triangleBoard,
  triangleGridBoard,
} from "./tilings";
import {
  archCylinderBoard,
  archKleinBoard,
  archMobiusBoard,
  archTorusBoard,
  cylinderBoard,
  cylinderHexBoard,
  cylinderTriangleBoard,
  kleinBoard,
  kleinHexBoard,
  kleinTriangleBoard,
  mobiusBoard,
  mobiusHexBoard,
  mobiusTriangleBoard,
  torusBoard,
  torusHexBoard,
  torusTriangleBoard,
} from "./surfaces";

// The Archimedean/Laves builders take the tiling key as their first argument,
// so a preset's args are a mix of that leading string and numbers. The dispatch
// map is intentionally loose (each concrete builder has its own signature).
type Arg = number | string;
type Builder = (...args: any[]) => AnyBoard;

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
  torus_board: torusBoard,
  torus_triangle_board: torusTriangleBoard,
  torus_hex_board: torusHexBoard,
  mobius_board: mobiusBoard,
  mobius_triangle_board: mobiusTriangleBoard,
  mobius_hex_board: mobiusHexBoard,
  klein_board: kleinBoard,
  klein_triangle_board: kleinTriangleBoard,
  klein_hex_board: kleinHexBoard,
  cylinder_board: cylinderBoard,
  cylinder_triangle_board: cylinderTriangleBoard,
  cylinder_hex_board: cylinderHexBoard,
  archimedean_board: archimedeanBoard,
  arch_torus_board: archTorusBoard,
  arch_cylinder_board: archCylinderBoard,
  arch_mobius_board: archMobiusBoard,
  arch_klein_board: archKleinBoard,
  penrose_board: penroseBoard,
  hat_board: hatBoard,
};

interface PresetSpec {
  builder: string;
  args: Record<string, Arg[]>;
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
