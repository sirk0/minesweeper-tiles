import { CanvasTexture, LinearFilter, SRGBColorSpace, Texture } from "three";

// A canvas-baked texture atlas of the cell glyphs (digits 1-8, flag, mine).
// One texture, sampled by UV quads over each cell, keeps the whole board to a
// couple of draw calls. Rebake (`makeGlyphAtlas`) when the device pixel ratio
// changes so glyphs stay crisp.

// A digit 1..12 (shared-vertex adjacency on triangles/hexagons can exceed 8),
// a flag, a mine, or a crossed-out flag (a misplaced flag revealed on loss).
// 0 means empty.
export type Glyph = number | "flag" | "mine" | "wrongFlag";

// Slot order in the atlas grid. Index 0 (empty) is intentionally blank.
// 16 slots fill the 4x4 grid exactly.
const SLOTS: Glyph[] = [
  0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, "flag", "mine", "wrongFlag",
];
const COLS = 4;
const ROWS = 4; // 4x4 = 16 slots, all used

// Classic minesweeper digit colours; 9+ reuse a neutral dark tone.
const DIGIT_COLORS: Record<number, string> = {
  1: "#2f6bff",
  2: "#2e9e3f",
  3: "#e5534b",
  4: "#1b2a78",
  5: "#8a1f1f",
  6: "#1f8a8a",
  7: "#202020",
  8: "#6b6b6b",
};

export interface GlyphAtlas {
  texture: Texture;
  /** UV rect [u0, v0, u1, v1] for a glyph, or null for empty. */
  uv(glyph: Glyph): [number, number, number, number] | null;
}

function slotIndex(glyph: Glyph): number {
  return SLOTS.indexOf(glyph);
}

export function makeGlyphAtlas(cellPx = 128): GlyphAtlas {
  const canvas = document.createElement("canvas");
  canvas.width = COLS * cellPx;
  canvas.height = ROWS * cellPx;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2d context unavailable for glyph atlas");

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  SLOTS.forEach((glyph, i) => {
    if (glyph === 0) return;
    const cx = (i % COLS) * cellPx + cellPx / 2;
    const cy = Math.floor(i / COLS) * cellPx + cellPx / 2;
    if (typeof glyph === "number") {
      ctx.fillStyle = DIGIT_COLORS[glyph] ?? "#202020";
      const scale = glyph >= 10 ? 0.5 : 0.7; // two digits fit narrower
      // Rubik (the pygame board font); falls back to sans-serif until loaded.
      ctx.font = `bold ${Math.round(cellPx * scale)}px "Rubik", sans-serif`;
      ctx.fillText(String(glyph), cx, cy + cellPx * 0.03);
    } else if (glyph === "flag") {
      drawFlag(ctx, cx, cy, cellPx);
    } else if (glyph === "wrongFlag") {
      drawFlag(ctx, cx, cy, cellPx);
      drawCross(ctx, cx, cy, cellPx);
    } else {
      drawMine(ctx, cx, cy, cellPx);
    }
  });

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearFilter;
  texture.needsUpdate = true;

  return {
    texture,
    uv(glyph) {
      const i = slotIndex(glyph);
      if (i < 0 || glyph === 0) return null;
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      const u0 = col / COLS;
      const u1 = (col + 1) / COLS;
      // Canvas y grows downward, texture v grows upward.
      const v1 = 1 - row / ROWS;
      const v0 = 1 - (row + 1) / ROWS;
      return [u0, v0, u1, v1];
    },
  };
}

function drawFlag(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  s: number,
): void {
  const poleX = cx - s * 0.08;
  ctx.strokeStyle = "#202020";
  ctx.lineWidth = s * 0.05;
  ctx.beginPath();
  ctx.moveTo(poleX, cy - s * 0.28);
  ctx.lineTo(poleX, cy + s * 0.3);
  ctx.stroke();
  // base
  ctx.fillStyle = "#202020";
  ctx.fillRect(cx - s * 0.22, cy + s * 0.28, s * 0.44, s * 0.08);
  // flag
  ctx.fillStyle = "#e5534b";
  ctx.beginPath();
  ctx.moveTo(poleX, cy - s * 0.28);
  ctx.lineTo(poleX + s * 0.28, cy - s * 0.14);
  ctx.lineTo(poleX, cy);
  ctx.closePath();
  ctx.fill();
}

/** A dark X across the cell — drawn over a flag to mark it as misplaced when
 * the board is revealed on loss (matches gui.py's `draw_flag(wrong=True)`). */
function drawCross(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  s: number,
): void {
  const r = s * 0.36;
  ctx.strokeStyle = "#222428"; // MINE_COLOR
  ctx.lineWidth = s * 0.08;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(cx - r, cy - r);
  ctx.lineTo(cx + r, cy + r);
  ctx.moveTo(cx - r, cy + r);
  ctx.lineTo(cx + r, cy - r);
  ctx.stroke();
}

function drawMine(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  s: number,
): void {
  const r = s * 0.26;
  ctx.strokeStyle = "#202020";
  ctx.lineWidth = s * 0.055;
  for (let k = 0; k < 8; k++) {
    const a = (k * Math.PI) / 4;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * r * 1.35, cy + Math.sin(a) * r * 1.35);
    ctx.stroke();
  }
  ctx.fillStyle = "#202020";
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
  // highlight
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(cx - r * 0.3, cy - r * 0.3, r * 0.28, 0, Math.PI * 2);
  ctx.fill();
}
