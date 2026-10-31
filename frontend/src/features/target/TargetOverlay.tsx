import { useRef, useState, type PointerEvent } from "react";
import { ApiError } from "../../api/client";
import { useDetections } from "../../api/queries";
import type { Box, Target, TargetInput, Video } from "../../api/types";
import { classLabel } from "../../lib/coco";
import { formatTime, percent } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import {
  boxFromPoints,
  frameIndex,
  frameTime,
  insideRect,
  sourceToStage,
  stageToSource,
  type Point,
} from "../../player/geometry";
import type { ViewerState } from "../../player/Viewer";
import s from "./TargetOverlay.module.css";

/** 아직 저장하지 않은 선택. */
export interface TargetDraft extends TargetInput {
  frame_index: number;
}

export interface TargetOverlayProps {
  state: ViewerState;
  video: Video;
  saved: Target | null;
  draft: TargetDraft | null;
  onPick: (draft: TargetDraft) => void;
}

/** 무대 픽셀로 이보다 작게 끌면 클릭으로 본다. */
const MIN_DRAG = 6;

function sameBox(a: Box, b: Box): boolean {
  return (
    Math.abs(a.x - b.x) < 1 &&
    Math.abs(a.y - b.y) < 1 &&
    Math.abs(a.width - b.width) < 1 &&
    Math.abs(a.height - b.height) < 1
  );
}

/** 화면 위쪽 끝에 붙은 박스는 이름표를 박스 안쪽에 둔다. */
function labelClass(top: number): string {
  return top < 28 ? `${s.label} ${s.inside}` : s.label;
}

/**
 * 멈춘 장면 위에 탐지 박스를 띄운다. 박스를 누르면 그 물체를, 빈 곳을 끌면
 * 직접 그린 영역을 고른다. 모드 전환은 없다.
 */
export function TargetOverlay({ state, video, saved, draft, onPick }: TargetOverlayProps) {
  const root = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ start: Point; end: Point } | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const media = { width: video.width ?? 1, height: video.height ?? 1 };
  const fps = video.proxy_fps;
  const index = frameIndex(state.time, fps);
  const settled = useDebounced(index, 250);
  const ready = state.paused && settled === index;
  const t = frameTime(index, fps);
  const detections = useDetections(video.id, index, t, ready);

  if (!state.paused) {
    return null;
  }

  const { frame } = state;
  const shown =
    draft && draft.frame_index === index
      ? draft
      : saved && saved.frame_index === index
        ? saved
        : null;
  const boxes = detections.data?.boxes ?? [];
  const shownIsDetection =
    shown?.source === "detect" && boxes.some((box) => sameBox(box.bbox, shown.bbox));

  function local(event: PointerEvent): Point {
    const rect = root.current?.getBoundingClientRect();
    return rect ? { x: event.clientX - rect.left, y: event.clientY - rect.top } : { x: 0, y: 0 };
  }

  /** 커서 아래 박스 중 가장 작은 것. 버스 안의 사람처럼 겹쳐도 안쪽 것을 고를 수 있다. */
  function hitTest(point: Point): number | null {
    if (!ready) {
      return null;
    }
    let best: number | null = null;
    let bestArea = Infinity;
    for (const [i, box] of boxes.entries()) {
      const area = box.bbox.width * box.bbox.height;
      if (area < bestArea && insideRect(point, sourceToStage(box.bbox, frame, media))) {
        best = i;
        bestArea = area;
      }
    }
    return best;
  }

  function pickDetection(i: number) {
    const box = boxes[i];
    if (box) {
      onPick({
        t,
        frame_index: index,
        bbox: box.bbox,
        source: "detect",
        class_name: box.class_name,
        confidence: box.confidence,
      });
    }
  }

  // 누른 채 끌면 직접 그리기, 제자리에서 떼면 그 자리의 박스 고르기.
  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    const point = local(event);
    if (event.button !== 0 || !insideRect(point, frame)) {
      return;
    }
    const source = stageToSource(point, frame, media);
    setDrag({ start: source, end: source });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const point = local(event);
    if (drag) {
      setDrag({ ...drag, end: stageToSource(point, frame, media) });
    } else {
      setHover(hitTest(point));
    }
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (!drag) {
      return;
    }
    const box = boxFromPoints(drag.start, drag.end, media);
    setDrag(null);
    const onStage = sourceToStage(box, frame, media);
    if (onStage.width >= MIN_DRAG && onStage.height >= MIN_DRAG) {
      onPick({ t, frame_index: index, bbox: box, source: "drag" });
      return;
    }
    const hit = hitTest(local(event));
    if (hit != null) {
      pickDetection(hit);
    }
  }

  let hint = "박스를 눌러 고르거나, 빈 곳을 끌어 직접 그리세요";
  if (!ready || detections.isFetching) {
    hint = "탐지 중…";
  } else if (detections.error) {
    hint =
      detections.error instanceof ApiError && detections.error.status === 503
        ? "탐지 모델이 없어 직접 그리기만 됩니다. 빈 곳을 끌어 고르세요"
        : `탐지하지 못했습니다: ${detections.error.message}`;
  } else if (detections.data && boxes.length === 0) {
    hint = "찾은 물체가 없습니다. 빈 곳을 끌어 직접 그리세요";
  }

  const dragBox = drag
    ? sourceToStage(boxFromPoints(drag.start, drag.end, media), frame, media)
    : null;
  const shownBox = shown && !shownIsDetection ? sourceToStage(shown.bbox, frame, media) : null;

  return (
    <div
      ref={root}
      className={s.overlay}
      style={{ cursor: hover != null && !drag ? "pointer" : undefined }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDrag(null)}
      onPointerLeave={() => setHover(null)}
    >
      {ready
        ? boxes.map((box, i) => {
            const rect = sourceToStage(box.bbox, frame, media);
            const selected = shown ? sameBox(shown.bbox, box.bbox) : false;
            const label = classLabel(box.class_name);
            const confidence = box.confidence != null ? percent(box.confidence) : "";
            return (
              <button
                key={`${index}-${i}`}
                type="button"
                className={s.box}
                data-selected={selected || undefined}
                data-hover={hover === i || undefined}
                style={{ left: rect.x, top: rect.y, width: rect.width, height: rect.height }}
                aria-label={`${label} 고르기, 신뢰도 ${confidence}`}
                aria-pressed={selected}
                // 마우스는 오버레이가 받는다(끌기와 겹친 박스 처리). 이 버튼은 키보드용이다.
                onClick={() => pickDetection(i)}
              >
                <span className={labelClass(rect.y)}>
                  {label} <span className="num">{confidence}</span>
                </span>
              </button>
            );
          })
        : null}
      {shownBox ? (
        <div
          className={s.chosen}
          style={{
            left: shownBox.x,
            top: shownBox.y,
            width: shownBox.width,
            height: shownBox.height,
          }}
          aria-hidden="true"
        >
          <span className={labelClass(shownBox.y)}>{classLabel(shown?.class_name)}</span>
        </div>
      ) : null}
      {dragBox ? (
        <div
          className={s.drawing}
          style={{ left: dragBox.x, top: dragBox.y, width: dragBox.width, height: dragBox.height }}
          aria-hidden="true"
        />
      ) : null}
      <div className={s.hint} aria-live="polite">
        {hint}
      </div>
      <div className={`${s.count} num`}>
        {ready && detections.data ? `탐지 ${boxes.length}개 · ` : ""}
        {formatTime(t)}
      </div>
    </div>
  );
}
