import type { AnalysisResult, Target, Video } from "../../api/types";
import { targetLabel } from "../../lib/coco";
import { formatSignal, sampleAt, SIGNALS } from "../../lib/signals";
import { sourceToStage } from "../../player/geometry";
import type { ViewerState } from "../../player/Viewer";
import s from "./TrackOverlay.module.css";

export interface TrackOverlayProps {
  state: ViewerState;
  video: Video;
  result: AnalysisResult;
  target: Target | null;
}

/** 재생하면서 추적 박스와 그 순간의 신호를 영상 위에 보여 준다. 클릭은 영상으로 통과한다. */
export function TrackOverlay({ state, video, result, target }: TrackOverlayProps) {
  const index = sampleAt(result, state.time);
  const samples = result.samples;
  const visible = samples.visible[index] ?? false;
  const media = { width: video.width ?? 1, height: video.height ?? 1 };
  const box =
    visible && samples.x[index] != null
      ? sourceToStage(
          {
            x: samples.x[index] ?? 0,
            y: samples.y[index] ?? 0,
            width: samples.w[index] ?? 0,
            height: samples.h[index] ?? 0,
          },
          state.frame,
          media,
        )
      : null;

  return (
    <div className={s.overlay} aria-hidden="true">
      {box ? (
        <div
          className={s.box}
          style={{ left: box.x, top: box.y, width: box.width, height: box.height }}
        >
          <span className={s.label}>{targetLabel(target)}</span>
        </div>
      ) : null}
      <div className={s.readout}>
        {visible ? (
          SIGNALS.map((info) => (
            <span key={info.key} className={s.chip}>
              <span className={s.swatch} style={{ background: info.color }} />
              {info.label}{" "}
              <span className="num">{formatSignal(info, samples[info.key][index] ?? 0)}</span>
            </span>
          ))
        ) : (
          <span className={s.chip}>대상이 화면에 없음</span>
        )}
      </div>
    </div>
  );
}
