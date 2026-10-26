import { useRef, useState, type CSSProperties, type PointerEvent } from "react";
import type { BBox, DetectionBox } from "../types";

export interface BoxSelectionOverlayProps {
  mode: "drag" | "detect";
  detections?: DetectionBox[];
  selected?: BBox | null;
  onDragSelect?: (bbox: BBox) => void;
  onDetectionClick?: (box: DetectionBox, index: number) => void;
}

export function BoxSelectionOverlay({
  mode,
  detections = [],
  selected = null,
  onDragSelect,
  onDetectionClick,
}: BoxSelectionOverlayProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const origin = useRef<{ x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<BBox | null>(null);

  function localPoint(event: PointerEvent<HTMLElement>): { x: number; y: number } {
    const rect = frameRef.current?.getBoundingClientRect();
    if (!rect) {
      return { x: 0, y: 0 };
    }
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (mode !== "drag") {
      return;
    }
    const point = localPoint(event);
    origin.current = point;
    setDraft({ x: point.x, y: point.y, width: 0, height: 0 });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!origin.current) {
      return;
    }
    const point = localPoint(event);
    const x = Math.min(origin.current.x, point.x);
    const y = Math.min(origin.current.y, point.y);
    setDraft({
      x,
      y,
      width: Math.abs(point.x - origin.current.x),
      height: Math.abs(point.y - origin.current.y),
    });
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (!origin.current) {
      return;
    }
    const point = localPoint(event);
    const x = Math.min(origin.current.x, point.x);
    const y = Math.min(origin.current.y, point.y);
    const next = {
      x,
      y,
      width: Math.abs(point.x - origin.current.x),
      height: Math.abs(point.y - origin.current.y),
    };
    origin.current = null;
    setDraft(null);
    if (next.width > 2 && next.height > 2) {
      onDragSelect?.(next);
    }
  }

  return (
    <div
      ref={frameRef}
      className="overlay"
      aria-label={mode === "drag" ? "드래그로 객체 선택" : "탐지 박스 선택"}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {mode === "detect"
        ? detections.map((box, index) => (
            <button
              key={`${box.bbox.x}-${box.bbox.y}-${index}`}
              type="button"
              className="overlay__box"
              style={{
                left: box.bbox.x,
                top: box.bbox.y,
                width: box.bbox.width,
                height: box.bbox.height,
              }}
              onClick={(event) => {
                event.stopPropagation();
                onDetectionClick?.(box, index);
              }}
            >
              {box.class_name ?? "객체"} {box.confidence != null ? box.confidence.toFixed(2) : ""}
            </button>
          ))
        : null}
      {mode === "drag" && (draft || selected) ? (
        <div className="overlay__box" style={boxStyle(draft ?? selected)} aria-hidden="true" />
      ) : null}
      <span className="muted" style={{ position: "absolute", left: 8, bottom: 8 }}>
        {mode === "drag" ? "마우스로 영역을 드래그합니다." : `탐지 박스 ${detections.length}개`}
      </span>
    </div>
  );
}

function boxStyle(box: BBox | null): CSSProperties {
  if (!box) {
    return { display: "none" };
  }
  return { left: box.x, top: box.y, width: box.width, height: box.height };
}
