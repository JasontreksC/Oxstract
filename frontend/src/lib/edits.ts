import type { Cut, SegmentEdit } from "../api/types";

/** 짧게는 남기지 않는다. 서버 app/segments.py MIN_PIECE 와 같다. */
export const MIN_PIECE = 0.1;

/** 새 편집을 끝에 붙인다. 새 범위 안에 통째로 들어가는 옛 편집은 의미가 없으니 뺀다. */
export function pushEdit(edits: SegmentEdit[], edit: SegmentEdit): SegmentEdit[] {
  if (edit.end - edit.start <= 0) {
    return edits;
  }
  return [...edits.filter((e) => e.start < edit.start || e.end > edit.end), edit];
}

/** 컷 하나의 끝을 옮긴 것을 편집으로 바꾼다. 늘리면 keep, 줄이면 drop. */
export function trimEdits(cut: Cut, start: number, end: number): SegmentEdit[] {
  const edits: SegmentEdit[] = [];
  if (start < cut.start) {
    edits.push({ op: "keep", start, end: cut.start });
  } else if (start > cut.start) {
    edits.push({ op: "drop", start: cut.start, end: start });
  }
  if (end > cut.end) {
    edits.push({ op: "keep", start: cut.end, end });
  } else if (end < cut.end) {
    edits.push({ op: "drop", start: end, end: cut.end });
  }
  return edits;
}

export function applyEdits(edits: SegmentEdit[], added: SegmentEdit[]): SegmentEdit[] {
  return added.reduce(pushEdit, edits);
}

export function cutAt(cuts: Cut[], t: number): number {
  return cuts.findIndex((cut) => t >= cut.start && t < cut.end);
}
