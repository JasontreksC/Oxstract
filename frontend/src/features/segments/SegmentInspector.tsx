import { Play, RotateCcw, Trash2, Undo2 } from "lucide-react";
import { useNavigate } from "react-router";
import { useRerunAnalysis } from "../../api/queries";
import type { AnalysisResult, Clip } from "../../api/types";
import { targetLabel } from "../../lib/coco";
import { formatTime, percent } from "../../lib/format";
import inspector from "../../editor/Inspector.module.css";
import type { CutEditor } from "./useCutEditor";
import s from "./SegmentInspector.module.css";

const PRESETS = [
  { label: "낮음", value: 0.6 },
  { label: "보통", value: 1 },
  { label: "높음", value: 1.6 },
];

export interface SegmentInspectorProps {
  clip: Clip;
  result: AnalysisResult | undefined;
  editor: CutEditor;
  onSeek: (t: number) => void;
  onPlayCut: (start: number) => void;
}

/** ③ 구간 단계 오른쪽: 민감도와 판정 설정, 결과 요약, 고른 컷. */
export function SegmentInspector({
  clip,
  result,
  editor,
  onSeek,
  onPlayCut,
}: SegmentInspectorProps) {
  const navigate = useNavigate();
  const rerun = useRerunAnalysis(clip.project_id);
  const params = editor.settings?.params;
  const duration = editor.view?.duration || clip.video.duration || 0;
  const kept = editor.cuts.reduce((sum, cut) => sum + cut.end - cut.start, 0);
  const cut = editor.cuts[editor.selected];
  const visible = result
    ? result.samples.visible.filter(Boolean).length / Math.max(1, result.samples.visible.length)
    : null;

  if (!params) {
    return <p className="muted">구간을 불러오는 중…</p>;
  }

  return (
    <>
      <div>
        <div className={inspector.kicker}>
          {clip.video.filename}
          {clip.target ? ` · 대상: ${targetLabel(clip.target)}` : ""}
        </div>
        <h2 className={inspector.heading}>남길 구간 기준</h2>
      </div>

      <div className={s.field}>
        <span className={s.label}>민감도</span>
        <div className={s.segmented} role="group" aria-label="민감도">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              aria-pressed={Math.abs(params.sensitivity - preset.value) < 0.01}
              onClick={() => editor.setParams({ sensitivity: preset.value })}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <fieldset className={s.checks}>
        <legend className={s.label}>움직임으로 볼 것</legend>
        <label>
          <input
            type="checkbox"
            checked={params.use_move}
            onChange={(event) => editor.setParams({ use_move: event.target.checked })}
          />
          <span className={s.swatch} style={{ background: "var(--color-signal-move)" }} />
          이동 <span className="muted">위치가 바뀌거나 다가오고 멀어짐</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={params.use_turn}
            onChange={(event) => editor.setParams({ use_turn: event.target.checked })}
          />
          <span className={s.swatch} style={{ background: "var(--color-signal-rotate)" }} />
          회전 <span className="muted">제자리에서 돌거나 몸을 돌림</span>
        </label>
      </fieldset>

      <label className={s.field}>
        <span className={s.row}>
          <span className={s.label}>짧은 멈춤 합치기</span>
          <span className="num">{params.merge_gap.toFixed(1)}초</span>
        </span>
        <input
          type="range"
          min={0}
          max={3}
          step={0.1}
          value={params.merge_gap}
          onChange={(event) => editor.setParams({ merge_gap: Number(event.target.value) })}
        />
      </label>
      <label className={s.field}>
        <span className={s.row}>
          <span className={s.label}>컷 앞뒤 여유</span>
          <span className="num">{params.padding.toFixed(1)}초</span>
        </span>
        <input
          type="range"
          min={0}
          max={2}
          step={0.1}
          value={params.padding}
          onChange={(event) => editor.setParams({ padding: Number(event.target.value) })}
        />
      </label>

      <details className={s.advanced}>
        <summary>고급: 민감도 숫자, 최소 컷 길이</summary>
        <label className={s.field}>
          <span className={s.row}>
            <span className={s.label}>민감도 (기준값을 이 수로 나눔)</span>
            <span className="num">{params.sensitivity.toFixed(2)}</span>
          </span>
          <input
            type="range"
            min={0.25}
            max={4}
            step={0.05}
            value={params.sensitivity}
            onChange={(event) => editor.setParams({ sensitivity: Number(event.target.value) })}
          />
        </label>
        <label className={s.field}>
          <span className={s.row}>
            <span className={s.label}>이보다 짧은 움직임은 버림</span>
            <span className="num">{params.min_length.toFixed(1)}초</span>
          </span>
          <input
            type="range"
            min={0}
            max={5}
            step={0.1}
            value={params.min_length}
            onChange={(event) => editor.setParams({ min_length: Number(event.target.value) })}
          />
        </label>
      </details>

      <div className={s.summary}>
        <div className={`${s.big} num`}>
          컷 {editor.cuts.length}개 · {kept.toFixed(1)}초
        </div>
        <div className="muted num">
          원본 {formatTime(duration)}의 {duration ? percent(kept / duration) : "–"}가 남습니다
          {editor.saving ? " · 저장 중" : ""}
        </div>
      </div>

      {cut ? (
        <div className={s.selected}>
          <div className={s.row}>
            <strong className="num">
              컷 {editor.selected + 1} · {formatTime(cut.start)}–{formatTime(cut.end)}
            </strong>
            <span className="muted num">{(cut.end - cut.start).toFixed(1)}초</span>
          </div>
          <div className={s.buttons}>
            <button type="button" className="btn" onClick={() => onPlayCut(cut.start)}>
              <Play size={14} aria-hidden="true" />이 컷 재생
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => {
                editor.edit([{ op: "drop", start: cut.start, end: cut.end }]);
                editor.select(null);
              }}
            >
              <Trash2 size={14} aria-hidden="true" />
              빼기
            </button>
          </div>
          <span className="dim" style={{ fontSize: 12 }}>
            I 시작을, O 끝을 지금 재생 위치로 · Delete 빼기
          </span>
        </div>
      ) : null}

      {editor.error ? <p className="error-text">{editor.error}</p> : null}
      <div className={inspector.spacer} />

      <div className={s.buttons}>
        <button type="button" className="btn" disabled={!editor.canUndo} onClick={editor.undo}>
          <Undo2 size={14} aria-hidden="true" />
          되돌리기
        </button>
        <button
          type="button"
          className="btn"
          disabled={!editor.settings?.edits.length}
          onClick={editor.resetEdits}
          title="손으로 고친 것을 모두 지우고 자동 구간만 남깁니다"
        >
          자동 구간으로
        </button>
      </div>
      <div className={s.analysis}>
        <span className="dim num">
          추적 {visible != null ? percent(visible) : "–"}
          {visible != null && visible < 0.8 ? " · 놓친 곳이 많음" : ""}
        </span>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => navigate(`/p/${clip.project_id}/target`)}
        >
          대상 다시 고르기
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={rerun.isPending}
          onClick={() => {
            onSeek(0);
            rerun.mutate(clip.id);
          }}
          title="같은 대상으로 처음부터 다시 분석합니다"
        >
          <RotateCcw size={14} aria-hidden="true" />
          다시 분석
        </button>
      </div>
    </>
  );
}
