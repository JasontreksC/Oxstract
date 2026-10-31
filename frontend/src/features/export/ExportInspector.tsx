import { useState } from "react";
import { Check, CircleAlert, Download, LoaderCircle, Play, Trash2 } from "lucide-react";
import { mediaUrl } from "../../api/client";
import { useCreateRender, useDeleteRender } from "../../api/queries";
import { isActive, type RenderSettings, type RenderView } from "../../api/types";
import inspector from "../../editor/Inspector.module.css";
import { formatBytes, formatDate, formatTime, percent } from "../../lib/format";
import seg from "../segments/SegmentInspector.module.css";
import s from "./ExportInspector.module.css";

const RESOLUTIONS: { value: RenderSettings["resolution"]; label: string }[] = [
  { value: "source", label: "원본 최대" },
  { value: "1080", label: "1080p" },
  { value: "720", label: "720p" },
];
const QUALITIES: { value: RenderSettings["quality"]; label: string }[] = [
  { value: "small", label: "작게" },
  { value: "mid", label: "보통" },
  { value: "high", label: "높게" },
];
/** 대략의 Mbps. 크기 예상용. */
const BITRATE = { source: 16, "1080": 8, "720": 4 };
const QUALITY_FACTOR = { small: 0.6, mid: 1, high: 1.6 };

export interface ExportInspectorProps {
  projectId: string;
  total: number | undefined;
  renders: RenderView[];
  playing: string | null;
  onPlay: (id: string) => void;
}

export function ExportInspector({
  projectId,
  total,
  renders,
  playing,
  onPlay,
}: ExportInspectorProps) {
  const [settings, setSettings] = useState<RenderSettings>({
    resolution: "1080",
    quality: "mid",
    audio: true,
  });
  const create = useCreateRender(projectId);
  const remove = useDeleteRender(projectId);
  const running = renders.find((render) => isActive(render.status));
  const estimate =
    total != null
      ? Math.max(
          1,
          Math.round((total * BITRATE[settings.resolution] * QUALITY_FACTOR[settings.quality]) / 8),
        )
      : null;

  return (
    <>
      <div>
        <div className={inspector.kicker}>결과 영상</div>
        <h2 className={inspector.heading}>내보내기</h2>
      </div>
      <div className={seg.field}>
        <span className={seg.label}>해상도</span>
        <div className={seg.segmented} role="group" aria-label="해상도">
          {RESOLUTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={settings.resolution === option.value}
              onClick={() => setSettings({ ...settings, resolution: option.value })}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      <div className={seg.field}>
        <span className={seg.label}>품질 (높을수록 오래 걸리고 큼)</span>
        <div className={seg.segmented} role="group" aria-label="품질">
          {QUALITIES.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={settings.quality === option.value}
              onClick={() => setSettings({ ...settings, quality: option.value })}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      <label className={s.check}>
        <input
          type="checkbox"
          checked={settings.audio}
          onChange={(event) => setSettings({ ...settings, audio: event.target.checked })}
        />
        오디오 포함
      </label>
      <div className={s.summary}>
        <div className="num" style={{ fontWeight: 600, fontSize: 15 }}>
          {total != null ? `${total.toFixed(1)}초` : "–"} · 약 {estimate ?? "–"} MB
        </div>
        <div className="muted">mp4 · H.264 · AAC · CPU로 인코딩합니다</div>
      </div>

      {running ? (
        <div className={s.running}>
          <div className={s.row}>
            <span>
              <LoaderCircle size={14} className="spin" aria-hidden="true" />{" "}
              {running.status === "queued"
                ? "렌더 대기 중"
                : `렌더 중 ${percent(running.progress)}`}
            </span>
            <button
              type="button"
              className="btn btn-ghost"
              style={{ height: 28 }}
              onClick={() => remove.mutate(running.id)}
            >
              취소
            </button>
          </div>
          <div className="bar">
            <span style={{ width: percent(running.progress) }} />
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="btn btn-primary btn-block"
          disabled={create.isPending}
          onClick={() => create.mutate(settings)}
        >
          렌더 시작
        </button>
      )}
      {create.error ? <p className="error-text">{create.error.message}</p> : null}

      <div className={s.history}>
        <span className={seg.label}>결과 목록</span>
        {renders.filter((render) => !isActive(render.status)).length === 0 ? (
          <p className="dim" style={{ fontSize: 12 }}>
            아직 결과가 없습니다.
          </p>
        ) : null}
        <ul>
          {renders
            .filter((render) => !isActive(render.status))
            .map((render) => (
              <li key={render.id} data-playing={render.id === playing || undefined}>
                {render.ready ? (
                  <Check size={14} color="var(--color-success)" aria-hidden="true" />
                ) : (
                  <CircleAlert size={14} color="var(--color-danger)" aria-hidden="true" />
                )}
                <span className={s.meta}>
                  <span className="num">
                    {formatDate(render.created_at)} ·{" "}
                    {RESOLUTIONS.find((r) => r.value === render.settings.resolution)?.label}
                  </span>
                  <span className="dim num">
                    {render.ready
                      ? `${formatTime(render.duration)} · ${formatBytes(render.size_bytes ?? 0)}`
                      : render.status === "canceled"
                        ? "취소됨"
                        : `실패: ${render.error ?? ""}`}
                  </span>
                </span>
                {render.ready ? (
                  <>
                    <button
                      type="button"
                      className="btn icon-btn"
                      aria-label="보기"
                      onClick={() => onPlay(render.id)}
                    >
                      <Play size={14} aria-hidden="true" />
                    </button>
                    <a
                      className="btn icon-btn"
                      aria-label="다운로드"
                      href={mediaUrl.render(render.id, true)}
                      download={render.filename}
                    >
                      <Download size={14} aria-hidden="true" />
                    </a>
                  </>
                ) : null}
                <button
                  type="button"
                  className="btn btn-ghost icon-btn"
                  aria-label="지우기"
                  onClick={() => {
                    if (window.confirm("이 결과 파일을 지울까요?")) {
                      remove.mutate(render.id);
                    }
                  }}
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </li>
            ))}
        </ul>
      </div>
    </>
  );
}

/** ⑤ 단계 가운데: 고른 결과(없으면 가장 최근 것)를 재생한다. */
export function RenderPlayer({ render }: { render: RenderView | undefined }) {
  return (
    <div className={s.stage}>
      {render ? (
        <video key={render.id} src={mediaUrl.render(render.id)} controls playsInline />
      ) : (
        <p className="muted">렌더가 끝나면 여기에서 결과를 볼 수 있습니다.</p>
      )}
    </div>
  );
}
