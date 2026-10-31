import { Check, LoaderCircle } from "lucide-react";
import { useNavigate } from "react-router";
import { mediaUrl } from "../../api/client";
import type { AnalysisState, Clip, Target, Video } from "../../api/types";
import { classLabel } from "../../lib/coco";
import { formatTime, percent } from "../../lib/format";
import inspector from "../../editor/Inspector.module.css";
import type { TargetDraft } from "./TargetOverlay";
import s from "./TargetInspector.module.css";

const CROP_WIDTH = 96;
const CROP_HEIGHT = 72;

/** 고른 영역만 잘라 보여 준다. 그 장면의 프레임 이미지를 배경으로 옮겨 그린다. */
function TargetCrop({ video, target }: { video: Video; target: TargetDraft | Target }) {
  const width = video.width ?? 1;
  const height = video.height ?? 1;
  const { bbox } = target;
  const scale = Math.min(CROP_WIDTH / bbox.width, CROP_HEIGHT / bbox.height);
  const offsetX = (CROP_WIDTH - bbox.width * scale) / 2 - bbox.x * scale;
  const offsetY = (CROP_HEIGHT - bbox.height * scale) / 2 - bbox.y * scale;
  return (
    <div
      className={s.crop}
      role="img"
      aria-label="고른 대상"
      style={{
        backgroundImage: `url(${mediaUrl.frame(video.id, target.t)})`,
        backgroundSize: `${width * scale}px ${height * scale}px`,
        backgroundPosition: `${offsetX}px ${offsetY}px`,
      }}
    />
  );
}

function TargetSummary({ video, target }: { video: Video; target: TargetDraft | Target }) {
  return (
    <div className={s.summary}>
      <TargetCrop video={video} target={target} />
      <div className={s.facts}>
        <span className={s.name}>{classLabel(target.class_name)}</span>
        <span className="muted num">
          {target.confidence != null ? `신뢰도 ${percent(target.confidence)} · ` : ""}
          {formatTime(target.t)} 장면
        </span>
        <span className="dim num">
          {Math.round(target.bbox.width)}×{Math.round(target.bbox.height)} px
        </span>
      </div>
    </div>
  );
}

/** 저장된 대상의 분석 진행. 끝나면 ③ 구간 단계로 안내한다. */
function AnalysisLine({ clip, analysis }: { clip: Clip; analysis: AnalysisState | null }) {
  const navigate = useNavigate();
  if (!analysis) {
    return null;
  }
  if (analysis.status === "queued" || analysis.status === "running") {
    return (
      <div className={s.analysis}>
        <span className="badge num" style={{ color: "var(--color-accent-strong)" }}>
          <LoaderCircle size={14} className="spin" aria-hidden="true" />
          {analysis.status === "queued" ? "분석 대기 중" : `분석 중 ${percent(analysis.progress)}`}
        </span>
        <div className="bar">
          <span style={{ width: percent(analysis.progress) }} />
        </div>
      </div>
    );
  }
  if (analysis.ready) {
    return (
      <button
        type="button"
        className="btn btn-block"
        onClick={() => navigate(`/p/${clip.project_id}/segments`)}
      >
        분석 끝남 · 움직임 보기
      </button>
    );
  }
  return (
    <p className="error-text">
      {analysis.status === "canceled"
        ? "분석을 취소했습니다."
        : `분석 실패: ${analysis.error ?? ""}`}
    </p>
  );
}

export interface TargetInspectorProps {
  clip: Clip;
  draft: TargetDraft | null;
  progress: { done: number; total: number };
  saving: boolean;
  error: string | null;
  onSave: () => void;
  onDiscard: () => void;
  onSeek: (t: number) => void;
  onClear: () => void;
}

export function TargetInspector({
  clip,
  draft,
  progress,
  saving,
  error,
  onSave,
  onDiscard,
  onSeek,
  onClear,
}: TargetInspectorProps) {
  const { video, target } = clip;
  return (
    <>
      <div>
        <div className={inspector.kicker}>
          {video.filename} · 대상 지정 {progress.done}/{progress.total}
        </div>
        <h2 className={inspector.heading}>추적할 대상</h2>
      </div>

      {draft ? (
        <>
          <TargetSummary video={video} target={draft} />
          {target ? <p className="dim">저장한 대상을 이것으로 바꿉니다.</p> : null}
          <div className={inspector.spacer} />
          <p className="dim" style={{ fontSize: 12 }}>
            저장하면 뒤에서 분석을 시작하고, 대상이 필요한 다음 클립으로 넘어갑니다.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={saving}
            onClick={onSave}
          >
            이 대상으로 정하기
          </button>
          <div className={s.row}>
            <button type="button" className="btn" onClick={() => onSeek(draft.t)}>
              그 장면 보기
            </button>
            <button type="button" className="btn btn-ghost" onClick={onDiscard}>
              취소
            </button>
          </div>
        </>
      ) : target ? (
        <>
          <TargetSummary video={video} target={target} />
          <span className="badge" style={{ color: "var(--color-success)" }}>
            <Check size={14} strokeWidth={3} aria-hidden="true" />
            저장됨
          </span>
          <AnalysisLine clip={clip} analysis={clip.analysis} />
          <p className="notice">다른 박스를 누르거나 새로 그리면 바꿀 수 있습니다.</p>
          <div className={inspector.spacer} />
          <button type="button" className="btn btn-block" onClick={() => onSeek(target.t)}>
            저장한 장면 보기
          </button>
          <button
            type="button"
            className="btn btn-danger btn-block"
            disabled={saving}
            onClick={onClear}
          >
            대상 지우기
          </button>
        </>
      ) : (
        <>
          <ol className={s.howto}>
            <li>따라갈 물체가 잘 보이는 장면에서 멈춥니다.</li>
            <li>뜨는 탐지 박스를 누르거나, 빈 곳을 끌어 직접 그립니다.</li>
            <li>여기서 확인하고 저장합니다.</li>
          </ol>
          <p className="dim" style={{ fontSize: 12 }}>
            단축키: Space 재생 · ← → 한 프레임 · Shift + ← → 1초
          </p>
        </>
      )}
      {error ? <p className="error-text">{error}</p> : null}
    </>
  );
}
