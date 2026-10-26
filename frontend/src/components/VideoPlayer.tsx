import type { ReactNode } from "react";

export interface VideoPlayerProps {
  src?: string;
  currentTime?: number;
  duration?: number;
  onTimeChange?: (time: number) => void;
  onSelectFrame?: (time: number) => void;
  children?: ReactNode;
}

export function VideoPlayer({
  src,
  currentTime = 0,
  duration = 0,
  onTimeChange,
  onSelectFrame,
  children,
}: VideoPlayerProps) {
  const span = duration > 0 ? duration : 1;
  return (
    <section className="panel video-player" aria-label="영상 미리보기">
      <div className="video-player__stage">
        {src ? (
          <video src={src} controls />
        ) : (
          <p className="video-player__empty muted">영상을 올리면 여기에서 고릅니다.</p>
        )}
        {children}
      </div>
      <div className="video-player__controls">
        <input
          type="range"
          min={0}
          max={span}
          step={0.1}
          value={Math.min(currentTime, span)}
          aria-label="재생 위치"
          onChange={(event) => onTimeChange?.(Number(event.target.value))}
        />
        <span className="muted">{currentTime.toFixed(1)}초</span>
        <button type="button" onClick={() => onSelectFrame?.(currentTime)}>
          이 장면에서 선택
        </button>
      </div>
    </section>
  );
}
