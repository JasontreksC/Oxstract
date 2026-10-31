import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from "react";
import { ChevronLeft, ChevronRight, LoaderCircle, Pause, Play, RotateCcw } from "lucide-react";
import { mediaUrl } from "../api/client";
import type { Video } from "../api/types";
import { formatTime, percent } from "../lib/format";
import { fitRect, frameIndex, frameTime, type Rect, type Size } from "./geometry";
import type { Playhead } from "./playhead";
import s from "./Viewer.module.css";

export interface ViewerHandle {
  /** 그 시각이 든 프레임의 가운데로 옮기고 멈춘다. */
  seek: (t: number) => void;
  play: () => void;
}

/** 오버레이가 받는 재생 상태. frame은 무대 안에서 영상이 그려진 자리다. */
export interface ViewerState {
  time: number;
  paused: boolean;
  frame: Rect;
  stage: Size;
}

export interface ViewerProps {
  video: Video;
  onRetryProxy?: () => void;
  /** 처음 열 때 이 시각으로 간다 (저장된 대상의 장면 등). */
  initialTime?: number;
  overlay?: (state: ViewerState) => ReactNode;
  /** 뷰어 밖(타임라인)에 재생 위치를 알린다. */
  playhead?: Playhead;
  /** 있으면 이 범위들만 이어 재생한다("컷만" 미리보기). 시각 순서. */
  playRanges?: [number, number][] | null;
  /** 재생 바 오른쪽에 붙일 컨트롤. */
  extraControls?: ReactNode;
  ref?: Ref<ViewerHandle>;
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

/**
 * 재생 바가 하나뿐인 플레이어. 재생 위치는 이 컴포넌트의 state 하나로 관리하고
 * <video>와 양방향으로 맞춘다. 클립이 바뀌면 부모가 key로 새로 만든다.
 */
export function Viewer({
  video,
  onRetryProxy,
  initialTime,
  overlay,
  playhead,
  playRanges,
  extraControls,
  ref,
}: ViewerProps) {
  const element = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [time, setTime] = useState(initialTime ?? 0);
  const [duration, setDuration] = useState(video.duration ?? 0);
  const [playing, setPlaying] = useState(false);
  const [stage, setStage] = useState<Size>({ width: 0, height: 0 });
  const proxy = video.proxy;
  const ready = proxy?.status === "done";
  const fps = video.proxy_fps;

  const seek = useCallback(
    (next: number) => {
      const end = duration || video.duration || 0;
      const index = frameIndex(Math.max(0, Math.min(end, next)), fps);
      const target = Math.min(frameTime(index, fps), Math.max(0, end - 0.5 / fps));
      const el = element.current;
      if (el) {
        el.pause();
        el.currentTime = target;
      }
      setTime(target);
    },
    [duration, video.duration, fps],
  );

  const step = useCallback(
    (frames: number) => seek(frameTime(frameIndex(time, fps) + frames, fps)),
    [seek, time, fps],
  );

  useImperativeHandle(
    ref,
    () => ({
      seek,
      play: () => void element.current?.play(),
    }),
    [seek],
  );

  useEffect(() => {
    playhead?.set(time);
  }, [playhead, time]);

  const ranges = useRef(playRanges);
  ranges.current = playRanges;

  const toggle = useCallback(() => {
    const el = element.current;
    if (!el) {
      return;
    }
    if (el.paused) {
      // 컷만 재생: 마지막 컷 뒤에서 누르면 처음 컷부터.
      const list = ranges.current;
      if (list?.length && !list.some(([, end]) => end > el.currentTime + 0.05)) {
        el.currentTime = list[0][0];
      }
      void el.play();
    } else {
      el.pause();
    }
  }, []);

  useEffect(() => {
    const node = stageRef.current;
    if (!node) {
      return;
    }
    const observer = new ResizeObserver(([entry]) => {
      if (entry) {
        setStage({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // 재생 중에는 timeupdate(초당 4번)보다 촘촘하게 시각을 갱신한다.
  useEffect(() => {
    if (!playing) {
      return;
    }
    let handle = 0;
    const tick = () => {
      const el = element.current;
      if (el) {
        const list = ranges.current;
        const now = el.currentTime;
        if (list?.length && !list.some(([start, end]) => now >= start - 0.05 && now < end)) {
          const next = list.find(([start]) => start > now);
          if (next) {
            el.currentTime = next[0];
          } else {
            el.pause();
          }
        }
        setTime(el.currentTime);
      }
      handle = requestAnimationFrame(tick);
    };
    handle = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(handle);
  }, [playing]);

  useEffect(() => {
    if (!ready) {
      return;
    }
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      if (event.key === " ") {
        event.preventDefault();
        toggle();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const direction = event.key === "ArrowLeft" ? -1 : 1;
        step(direction * (event.shiftKey ? fps : 1));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready, fps, step, toggle]);

  const frame = fitRect(stage, {
    width: video.width ?? 16,
    height: video.height ?? 9,
  });

  return (
    <section className={s.viewer} aria-label="뷰어">
      <div className={s.stage} ref={stageRef}>
        {ready ? (
          <video
            ref={element}
            src={mediaUrl.proxy(video.id)}
            preload="auto"
            playsInline
            onClick={toggle}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onLoadedMetadata={(event) => {
              setDuration(event.currentTarget.duration);
              if (initialTime) {
                event.currentTarget.currentTime = initialTime;
              }
            }}
            onTimeUpdate={(event) => {
              if (!playing) {
                setTime(event.currentTarget.currentTime);
              }
            }}
          />
        ) : (
          <div className={s.placeholder}>
            {proxy?.status === "failed" || proxy?.status === "canceled" ? (
              <>
                <p>미리보기를 만들지 못했습니다.</p>
                {proxy.error ? <p className="dim">{proxy.error}</p> : null}
                {onRetryProxy ? (
                  <button type="button" className="btn" onClick={onRetryProxy}>
                    <RotateCcw size={14} aria-hidden="true" />
                    다시 만들기
                  </button>
                ) : null}
              </>
            ) : (
              <>
                <LoaderCircle size={28} className="spin" aria-hidden="true" />
                <p>
                  {proxy?.status === "running"
                    ? `미리보기 만드는 중 ${percent(proxy.progress)}`
                    : "미리보기 대기 중"}
                </p>
                <p className="dim">휴대폰 영상도 브라우저에서 재생되도록 변환합니다.</p>
              </>
            )}
          </div>
        )}
        {ready && overlay ? overlay({ time, paused: !playing, frame, stage }) : null}
        <span className={s.tag}>{video.filename}</span>
      </div>
      <div className={s.controls}>
        <button
          type="button"
          className="btn btn-primary icon-btn"
          style={{ height: 36 }}
          aria-label={playing ? "일시정지" : "재생"}
          disabled={!ready}
          onClick={toggle}
        >
          {playing ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
        </button>
        <button
          type="button"
          className="btn icon-btn"
          aria-label="이전 프레임"
          disabled={!ready}
          onClick={() => step(-1)}
        >
          <ChevronLeft size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="btn icon-btn"
          aria-label="다음 프레임"
          disabled={!ready}
          onClick={() => step(1)}
        >
          <ChevronRight size={16} aria-hidden="true" />
        </button>
        <span className={`${s.time} num`}>
          {formatTime(time)} <span className="dim">/ {formatTime(duration)}</span>
        </span>
        <input
          type="range"
          className={s.scrubber}
          aria-label="재생 위치"
          min={0}
          max={duration || 0}
          step="any"
          value={Math.min(time, duration || 0)}
          disabled={!ready}
          onChange={(event) => seek(Number(event.target.value))}
        />
        {extraControls}
      </div>
    </section>
  );
}
