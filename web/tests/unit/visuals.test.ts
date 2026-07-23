import { describe, expect, it } from "vitest";
import { baseColorFor, glyphFor, type CellVisual } from "../../src/render/boardMesh";

// The per-cell visual vocabulary shared by the flat and 3D board meshes. Guards
// the glyph/colour mapping — in particular the crossed-out "wrongFlag" shown on
// a misplaced flag when the board is revealed on loss.
describe("cell visuals", () => {
  it("maps every visual kind to a glyph", () => {
    expect(glyphFor({ kind: "hidden" })).toBeNull();
    expect(glyphFor({ kind: "flagged" })).toBe("flag");
    expect(glyphFor({ kind: "wrongFlag" })).toBe("wrongFlag");
    expect(glyphFor({ kind: "mine" })).toBe("mine");
    expect(glyphFor({ kind: "exploded" })).toBe("mine");
    expect(glyphFor({ kind: "revealed", mines: 0 })).toBeNull();
    expect(glyphFor({ kind: "revealed", mines: 3 })).toBe(3);
  });

  it("a misplaced flag keeps the tile colour of a normal flag", () => {
    expect(baseColorFor({ kind: "wrongFlag" })).toBe(baseColorFor({ kind: "flagged" }));
  });

  it("returns a colour for every kind (exhaustive switch)", () => {
    const kinds: CellVisual[] = [
      { kind: "hidden" },
      { kind: "flagged" },
      { kind: "wrongFlag" },
      { kind: "revealed", mines: 1 },
      { kind: "mine" },
      { kind: "exploded" },
    ];
    for (const v of kinds) expect(baseColorFor(v)).toBeDefined();
  });
});
