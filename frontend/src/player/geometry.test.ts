import { describe, expect, it } from "vitest";
import {
  boxFromPoints,
  fitRect,
  frameIndex,
  frameTime,
  insideRect,
  sourceToStage,
  stageToSource,
} from "./geometry";

describe("fitRect", () => {
  it("letterboxes a vertical video inside a wide stage", () => {
    expect(fitRect({ width: 1600, height: 900 }, { width: 1080, height: 1920 })).toEqual({
      x: (1600 - 506.25) / 2,
      y: 0,
      width: 506.25,
      height: 900,
    });
  });

  it("pillarboxes nothing when aspect ratios match", () => {
    expect(fitRect({ width: 800, height: 450 }, { width: 1920, height: 1080 })).toEqual({
      x: 0,
      y: 0,
      width: 800,
      height: 450,
    });
  });

  it("is empty before the stage has a size", () => {
    expect(fitRect({ width: 0, height: 0 }, { width: 1920, height: 1080 }).width).toBe(0);
  });
});

describe("stage and source coordinates", () => {
  const media = { width: 1080, height: 1920 };
  const frame = fitRect({ width: 1600, height: 900 }, media);

  it("maps a stage point into source pixels, ignoring the letterbox", () => {
    const point = stageToSource({ x: frame.x + frame.width / 2, y: 450 }, frame, media);
    expect(point.x).toBeCloseTo(540);
    expect(point.y).toBeCloseTo(960);
  });

  it("round-trips a source box", () => {
    const box = { x: 100, y: 200, width: 300, height: 400 };
    const stage = sourceToStage(box, frame, media);
    const topLeft = stageToSource({ x: stage.x, y: stage.y }, frame, media);
    const bottomRight = stageToSource(
      { x: stage.x + stage.width, y: stage.y + stage.height },
      frame,
      media,
    );
    expect(topLeft.x).toBeCloseTo(100);
    expect(topLeft.y).toBeCloseTo(200);
    expect(bottomRight.x).toBeCloseTo(400);
    expect(bottomRight.y).toBeCloseTo(600);
  });

  it("builds a drag box in any direction and clips it to the frame", () => {
    expect(boxFromPoints({ x: 500, y: 50 }, { x: -20, y: 300 }, media)).toEqual({
      x: 0,
      y: 50,
      width: 500,
      height: 250,
    });
  });

  it("tells whether a stage point is on the picture", () => {
    expect(insideRect({ x: frame.x - 1, y: 10 }, frame)).toBe(false);
    expect(insideRect({ x: frame.x + 1, y: 10 }, frame)).toBe(true);
  });
});

describe("frame snapping", () => {
  it("matches the server's frame index and middle time", () => {
    expect(frameIndex(0, 30)).toBe(0);
    expect(frameIndex(1.23, 10)).toBe(12);
    expect(frameIndex(0.3, 10)).toBe(3); // 0.3 * 10 is 2.9999999999999996 in floating point
    expect(frameTime(12, 10)).toBeCloseTo(1.25);
    expect(frameIndex(frameTime(12, 10), 10)).toBe(12);
  });
});
