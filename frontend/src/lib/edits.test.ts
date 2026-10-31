import { describe, expect, it } from "vitest";
import { applyEdits, cutAt, pushEdit, trimEdits } from "./edits";

const cut = { start: 2, end: 5, score: 0.5, edited: false };

describe("trimEdits", () => {
  it("keeps what an edge grew into and drops what it left", () => {
    expect(trimEdits(cut, 1, 4)).toEqual([
      { op: "keep", start: 1, end: 2 },
      { op: "drop", start: 4, end: 5 },
    ]);
    expect(trimEdits(cut, 3, 6)).toEqual([
      { op: "drop", start: 2, end: 3 },
      { op: "keep", start: 5, end: 6 },
    ]);
    expect(trimEdits(cut, 2, 5)).toEqual([]);
  });
});

describe("pushEdit", () => {
  it("forgets older edits inside the new range", () => {
    const edits = [
      { op: "keep" as const, start: 3, end: 4 },
      { op: "drop" as const, start: 0, end: 10 },
    ];
    expect(pushEdit(edits, { op: "drop", start: 2, end: 5 })).toEqual([
      { op: "drop", start: 0, end: 10 },
      { op: "drop", start: 2, end: 5 },
    ]);
  });

  it("ignores empty ranges", () => {
    expect(pushEdit([], { op: "keep", start: 3, end: 3 })).toEqual([]);
  });
});

describe("applyEdits and cutAt", () => {
  it("adds several edits in order", () => {
    expect(applyEdits([], trimEdits(cut, 1, 6))).toHaveLength(2);
  });

  it("finds the cut under a time", () => {
    expect(cutAt([cut], 2)).toBe(0);
    expect(cutAt([cut], 5)).toBe(-1);
  });
});
