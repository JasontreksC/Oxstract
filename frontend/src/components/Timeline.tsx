import type { Segment, TransitionAfter } from "../types";

export interface TimelineProps {
  segments: Segment[];
  duration: number;
  selectedIndex?: number | null;
  onSelectSegment?: (index: number) => void;
  onApplyTransitionToAll?: (transition: TransitionAfter) => void;
}

export function Timeline({
  segments,
  duration,
  selectedIndex = null,
  onSelectSegment,
  onApplyTransitionToAll,
}: TimelineProps) {
  const span = duration > 0 ? duration : 1;
  const selected =
    selectedIndex != null && selectedIndex < segments.length - 1
      ? segments[selectedIndex]?.transition_after
      : null;

  return (
    <section className="panel" aria-label="구간 타임라인">
      <div className="row">
        <strong>타임라인</strong>
        <span className="muted">{segments.length}개 컷</span>
      </div>
      <div className="timeline__track">
        {segments.map((segment, index) => {
          const left = (segment.start / span) * 100;
          const width = ((segment.end - segment.start) / span) * 100;
          const transition = segment.transition_after;
          return (
            <span key={`${segment.start}-${segment.end}`}>
              <button
                type="button"
                className="timeline__segment"
                style={{ left: `${left}%`, width: `${Math.max(width, 1)}%` }}
                aria-pressed={selectedIndex === index}
                aria-label={`${segment.start.toFixed(1)}초부터 ${segment.end.toFixed(1)}초`}
                onClick={() => onSelectSegment?.(index)}
              />
              {transition && index < segments.length - 1 ? (
                <span
                  className="timeline__transition"
                  data-type={transition.type}
                  style={{ left: `${(segment.end / span) * 100}%` }}
                  title={transitionLabel(transition)}
                />
              ) : null}
            </span>
          );
        })}
      </div>
      <button
        type="button"
        disabled={!selected}
        onClick={() => {
          if (selected) {
            onApplyTransitionToAll?.(selected);
          }
        }}
      >
        선택 전환을 마지막 컷 제외 전체에 적용
      </button>
    </section>
  );
}

function transitionLabel(transition: TransitionAfter): string {
  if (transition.type === "fade") {
    return `페이드 ${transition.duration}초`;
  }
  if (transition.type === "text_card") {
    return `텍스트 카드 ${transition.duration}초`;
  }
  return "효과 없음";
}
