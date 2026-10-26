/**
 * 시간순 움직임 구간.
 * JSON Schema: schemas/segment.schema.json, schemas/segment-list.schema.json
 * 마지막 요소의 transition_after는 null이거나 생략한다.
 */

import type { TransitionAfter } from "./transition";

export interface Segment {
  start: number;
  end: number;
  score: number;
  transition_after?: TransitionAfter | null;
}

export interface SegmentList {
  segments: Segment[];
}
