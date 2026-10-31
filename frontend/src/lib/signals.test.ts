import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "../api/types";
import { sampleAt, secondsAbove, SIGNALS } from "./signals";

function result(t: number[], move: number[]): AnalysisResult {
  const empty = t.map(() => null);
  return {
    version: 1,
    proxy_fps: 30,
    sample_fps: 10,
    target_frame: 0,
    target_class: null,
    samples: {
      t,
      x: empty,
      y: empty,
      w: empty,
      h: empty,
      visible: t.map(() => true),
      move,
      turn: t.map(() => 0),
      flow: t.map(() => 0),
    },
  };
}

describe("sampleAt", () => {
  const data = result([0.05, 0.15, 0.25, 0.35], [0, 0, 0, 0]);

  it("finds the nearest sample", () => {
    expect(sampleAt(data, 0)).toBe(0);
    expect(sampleAt(data, 0.16)).toBe(1);
    expect(sampleAt(data, 0.21)).toBe(2);
    expect(sampleAt(data, 9)).toBe(3);
  });
});

describe("secondsAbove", () => {
  it("counts samples over the reference at the sample rate", () => {
    const move = SIGNALS[0];
    expect(secondsAbove(result([0, 0.1, 0.2, 0.3], [0.1, 0.3, 0.5, 0.2]), move)).toBeCloseTo(0.2);
  });
});
