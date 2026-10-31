import type { Clip } from "../../api/types";
import { formatDuration } from "../../lib/format";
import s from "./ResultOrder.module.css";

/** 클립을 길이 비율로 늘어놓아 결과 영상의 순서를 보여 준다. */
export function ResultOrder({ clips }: { clips: Clip[] }) {
  return (
    <>
      <div className={s.header}>
        <span className={s.heading}>결과 순서</span>
        <span className="muted">분석이 끝나면 각 클립에서 남는 구간만 이 순서로 이어집니다</span>
      </div>
      {clips.length ? (
        <ol className={s.bar}>
          {clips.map((clip, index) => (
            <li
              key={clip.id}
              className={s.block}
              style={{ flexGrow: Math.max(1, clip.video.duration ?? 1) }}
              title={clip.video.filename}
            >
              <span className="dim num">{index + 1}</span>
              <span className={s.name}>{clip.video.filename}</span>
              <span className="muted num">
                {clip.cuts
                  ? `${clip.cuts.reduce((sum, cut) => sum + cut.end - cut.start, 0).toFixed(1)}초 남음`
                  : formatDuration(clip.video.duration)}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className={`${s.empty} dim`}>영상을 추가하면 여기에 순서가 나타납니다.</p>
      )}
    </>
  );
}
