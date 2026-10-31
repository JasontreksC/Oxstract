import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { Pencil } from "lucide-react";
import type { AnalysisResult } from "../../api/types";
import { MIN_PIECE, trimEdits } from "../../lib/edits";
import { formatTime } from "../../lib/format";
import { SIGNALS, type SignalKey } from "../../lib/signals";
import { usePlayhead, type Playhead } from "../../player/playhead";
import type { CutEditor } from "./useCutEditor";
import s from "./SegmentTimeline.module.css";

export interface SegmentTimelineProps {
  title: string;
  result: AnalysisResult;
  duration: number;
  editor: CutEditor;
  playhead: Playhead;
  onSeek: (t: number) => void;
}

/** 그래프 세로: 신호 ÷ (2 × 기준값). 민감도 1의 기준이 가운데(50%)다. */
function levelToTop(level: number): number {
  return 98 - Math.min(1, Math.max(0, level)) * 96;
}

function polyline(result: AnalysisResult, key: SignalKey, reference: number, span: number) {
  const values = result.samples[key];
  return result.samples.t
    .map((time, i) => {
      const x = ((time / span) * 1000).toFixed(1);
      return `${x},${levelToTop((values[i] ?? 0) / (2 * reference)).toFixed(1)}`;
    })
    .join(" ");
}

function lostRuns(result: AnalysisResult): [number, number][] {
  const { t, visible } = result.samples;
  const half = 0.5 / result.sample_fps;
  const runs: [number, number][] = [];
  let start: number | null = null;
  visible.forEach((seen, i) => {
    if (!seen && start == null) {
      start = Math.max(0, (t[i] ?? 0) - half);
    }
    if (seen && start != null) {
      runs.push([start, (t[i] ?? 0) - half]);
      start = null;
    }
  });
  if (start != null) {
    runs.push([start, (t.at(-1) ?? 0) + half]);
  }
  return runs;
}

function Playline({ playhead, span }: { playhead: Playhead; span: number }) {
  const time = usePlayhead(playhead);
  return (
    <span
      className={s.playline}
      style={{ left: `${(Math.min(time, span) / span) * 100}%` }}
      aria-hidden="true"
    />
  );
}

type Drag =
  | { kind: "resize"; index: number; edge: "start" | "end"; start: number; end: number }
  | { kind: "create"; anchor: number; current: number }
  | { kind: "threshold" };

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

/**
 * ③ 구간 단계의 타임라인. 위는 움직임 그래프와 기준선(위아래로 끌어 민감도 조절),
 * 아래는 남길 구간 띠(끝을 끌어 길이 조정, 빈 곳을 끌어 새 구간, 눌러서 고르기).
 */
export function SegmentTimeline({
  title,
  result,
  duration,
  editor,
  playhead,
  onSeek,
}: SegmentTimelineProps) {
  const span = duration > 0 ? duration : (result.samples.t.at(-1) ?? 1);
  const band = useRef<HTMLDivElement>(null);
  const graph = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [hidden, setHidden] = useState<Set<SignalKey>>(new Set());
  const params = editor.settings?.params;
  const sensitivity = params?.sensitivity ?? 1;

  const lines = useMemo(
    () =>
      SIGNALS.map((info) => ({
        ...info,
        points: polyline(result, info.key, info.reference, span),
      })),
    [result, span],
  );
  const lost = useMemo(() => lostRuns(result), [result]);
  const ticks = useMemo(() => {
    const every = span > 600 ? 120 : span > 120 ? 30 : span > 30 ? 10 : span > 10 ? 2 : 1;
    const list: number[] = [];
    for (let t = 0; t <= span; t += every) {
      list.push(t);
    }
    return list;
  }, [span]);

  // Delete 빼기, Ctrl+Z 되돌리기, I/O 고른 컷의 시작·끝을 재생 위치로.
  const { selected, cuts, edit, undo, select } = editor;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target)) {
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }
      const cut = cuts[selected];
      if (!cut) {
        return;
      }
      const now = playhead.get();
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        edit([{ op: "drop", start: cut.start, end: cut.end }]);
        select(null);
      } else if (event.key.toLowerCase() === "i" && now < cut.end - MIN_PIECE) {
        edit(trimEdits(cut, now, cut.end));
        select((now + cut.end) / 2);
      } else if (event.key.toLowerCase() === "o" && now > cut.start + MIN_PIECE) {
        edit(trimEdits(cut, cut.start, now));
        select((cut.start + now) / 2);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cuts, selected, edit, undo, select, playhead]);

  function timeAt(event: PointerEvent, element: HTMLElement | null): number {
    const rect = element?.getBoundingClientRect();
    if (!rect || rect.width === 0) {
      return 0;
    }
    return Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * span;
  }

  function startDrag(event: PointerEvent, next: Drag, element: HTMLElement | null) {
    event.stopPropagation();
    element?.setPointerCapture(event.pointerId);
    setDrag(next);
  }

  function onBandMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag) {
      return;
    }
    const t = timeAt(event, band.current);
    if (drag.kind === "resize") {
      setDrag(
        drag.edge === "start"
          ? { ...drag, start: Math.min(t, drag.end - MIN_PIECE) }
          : { ...drag, end: Math.max(t, drag.start + MIN_PIECE) },
      );
    } else if (drag.kind === "create") {
      setDrag({ ...drag, current: t });
    }
  }

  function onBandUp() {
    if (!drag) {
      return;
    }
    setDrag(null);
    if (drag.kind === "resize") {
      const cut = cuts[drag.index];
      if (cut) {
        edit(trimEdits(cut, drag.start, drag.end));
        select((drag.start + drag.end) / 2);
      }
    } else if (drag.kind === "create") {
      const start = Math.min(drag.anchor, drag.current);
      const end = Math.max(drag.anchor, drag.current);
      if (end - start >= 0.2) {
        edit([{ op: "keep", start, end }]);
        select((start + end) / 2);
      } else {
        select(null);
        onSeek(drag.anchor);
      }
    }
  }

  function onGraphMove(event: PointerEvent<HTMLDivElement>) {
    if (drag?.kind === "threshold") {
      const rect = graph.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      const top = ((event.clientY - rect.top) / rect.height) * 100;
      const level = Math.max(0.125, Math.min(0.98, (98 - top) / 96));
      editor.setParams({
        sensitivity: Math.round(Math.min(4, Math.max(0.25, 0.5 / level)) * 100) / 100,
      });
    } else if (event.buttons === 1 && !drag) {
      onSeek(timeAt(event, graph.current));
    }
  }

  const shown = cuts.map((cut, index) =>
    drag?.kind === "resize" && drag.index === index
      ? { ...cut, start: drag.start, end: drag.end }
      : cut,
  );
  const creating =
    drag?.kind === "create"
      ? { start: Math.min(drag.anchor, drag.current), end: Math.max(drag.anchor, drag.current) }
      : null;
  const thresholdTop = levelToTop(0.5 / sensitivity);
  const pct = (t: number) => `${(t / span) * 100}%`;
  const muted = (key: SignalKey) =>
    hidden.has(key) || (key === "move" ? params?.use_move === false : params?.use_turn === false);

  return (
    <>
      <div className={s.header}>
        <span className={s.title}>{title}</span>
        {lines.map((line) => (
          <button
            key={line.key}
            type="button"
            className={s.legend}
            aria-pressed={!hidden.has(line.key)}
            title={line.help}
            onClick={() =>
              setHidden((current) => {
                const next = new Set(current);
                if (next.has(line.key)) {
                  next.delete(line.key);
                } else {
                  next.add(line.key);
                }
                return next;
              })
            }
          >
            <span className={s.swatch} style={{ background: line.color }} />
            {line.label}
          </button>
        ))}
        <span className={s.legendStatic}>
          <span className={s.dash} />
          기준선
        </span>
        <span className={s.legendStatic}>
          <span className={s.keptSwatch} />
          남는 구간
        </span>
        <span className={`${s.hint} dim`}>
          기준선을 위아래로 끌어 민감도 · 구간 끝을 끌어 길이 · 빈 곳을 끌어 새 구간 · Delete 빼기
        </span>
      </div>
      <div className={s.grid}>
        <span />
        <div className={s.ruler}>
          {ticks.map((t, i) => (
            <span
              key={t}
              className="num"
              style={{ left: pct(t), transform: i ? "translateX(-50%)" : "none" }}
            >
              {formatTime(t).replace(/\.\d$/, "")}
            </span>
          ))}
        </div>

        <span className={s.rowLabel}>움직임</span>
        <div
          ref={graph}
          className={s.graph}
          title="눌러서 그 시각으로 이동"
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            onSeek(timeAt(event, graph.current));
          }}
          onPointerMove={onGraphMove}
          onPointerUp={() => drag?.kind === "threshold" && setDrag(null)}
        >
          {shown.map((cut) => (
            <span
              key={`k-${cut.start}`}
              className={s.keptShade}
              style={{ left: pct(cut.start), width: pct(cut.end - cut.start) }}
            />
          ))}
          {lost.map(([start, end]) => (
            <span
              key={`l-${start}`}
              className={s.lost}
              style={{ left: pct(start), width: pct(end - start) }}
            />
          ))}
          <svg viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">
            {lines.map((line) =>
              hidden.has(line.key) ? null : (
                <polyline
                  key={line.key}
                  points={line.points}
                  fill="none"
                  stroke={line.color}
                  strokeOpacity={muted(line.key) ? 0.25 : 1}
                  strokeWidth={1.5}
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              ),
            )}
          </svg>
          <span className={s.threshold} style={{ top: `${thresholdTop}%` }} aria-hidden="true" />
          <button
            type="button"
            className={s.thresholdHandle}
            style={{ top: `${thresholdTop}%` }}
            aria-label={`민감도 ${sensitivity.toFixed(2)}. 위아래로 끌어 조절`}
            onPointerDown={(event) => startDrag(event, { kind: "threshold" }, graph.current)}
            onKeyDown={(event) => {
              if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                event.preventDefault();
                const step = event.key === "ArrowUp" ? -0.1 : 0.1;
                editor.setParams({
                  sensitivity:
                    Math.round(Math.min(4, Math.max(0.25, sensitivity + step)) * 100) / 100,
                });
              }
            }}
          >
            민감도 <span className="num">{sensitivity.toFixed(2)}</span>
          </button>
          <Playline playhead={playhead} span={span} />
        </div>

        <span className={s.rowLabel}>구간</span>
        <div
          ref={band}
          className={s.band}
          onPointerDown={(event) => {
            const t = timeAt(event, band.current);
            startDrag(event, { kind: "create", anchor: t, current: t }, band.current);
          }}
          onPointerMove={onBandMove}
          onPointerUp={onBandUp}
          onPointerCancel={() => setDrag(null)}
        >
          {shown.map((cut, index) => (
            <div
              key={`c-${index}-${cut.start}`}
              className={s.cut}
              data-selected={index === selected || undefined}
              style={{ left: pct(cut.start), width: pct(cut.end - cut.start) }}
              onPointerDown={(event) => {
                event.stopPropagation();
                select((cut.start + cut.end) / 2);
                onSeek(cut.start);
              }}
              title={`${formatTime(cut.start)}–${formatTime(cut.end)}`}
            >
              <span
                className={`${s.handle} ${s.left}`}
                onPointerDown={(event) =>
                  startDrag(
                    event,
                    { kind: "resize", index, edge: "start", start: cut.start, end: cut.end },
                    band.current,
                  )
                }
              />
              <span className={s.cutLabel}>
                {index + 1}
                {cut.edited ? <Pencil size={10} aria-label="손으로 고침" /> : null}
              </span>
              <span
                className={`${s.handle} ${s.right}`}
                onPointerDown={(event) =>
                  startDrag(
                    event,
                    { kind: "resize", index, edge: "end", start: cut.start, end: cut.end },
                    band.current,
                  )
                }
              />
            </div>
          ))}
          {creating ? (
            <div
              className={s.creating}
              style={{ left: pct(creating.start), width: pct(creating.end - creating.start) }}
            />
          ) : null}
          <Playline playhead={playhead} span={span} />
        </div>
      </div>
    </>
  );
}
