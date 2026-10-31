import { LoaderCircle } from "lucide-react";
import { useNavigate } from "react-router";
import { useRerunAnalysis } from "../../api/queries";
import { locating, type Clip } from "../../api/types";
import { targetLabel } from "../../lib/coco";
import { percent } from "../../lib/format";
import inspector from "../../editor/Inspector.module.css";
import s from "./AnalysisInspector.module.css";

/** ③ 구간 단계 오른쪽, 분석이 아직이거나 실패한 클립. 끝난 클립은 SegmentInspector. */
export function AnalysisInspector({ clip }: { clip: Clip }) {
  const navigate = useNavigate();
  const rerun = useRerunAnalysis(clip.project_id);
  const { analysis, target } = clip;
  const header = (
    <div>
      <div className={inspector.kicker}>
        {clip.video.filename}
        {target ? ` · 대상: ${targetLabel(target)}` : ""}
      </div>
      <h2 className={inspector.heading}>움직임 분석</h2>
    </div>
  );

  if (!target && !locating(clip)) {
    return (
      <>
        {header}
        <p className={analysis?.status === "failed" ? "error-text" : "notice"}>
          {analysis?.status === "failed"
            ? (analysis.error ?? "이 영상에서 대상을 찾지 못했습니다.")
            : "이 클립은 아직 대상이 없습니다."}
        </p>
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={() => navigate(`/p/${clip.project_id}/target`)}
        >
          대상 지정으로
        </button>
      </>
    );
  }

  if (!analysis || analysis.status === "queued" || analysis.status === "running") {
    const progress = analysis?.progress ?? 0;
    return (
      <>
        {header}
        <div className={s.status}>
          <LoaderCircle size={16} className="spin" aria-hidden="true" />
          {analysis?.status === "running"
            ? `${target ? "분석" : "대상 찾는"} 중 ${percent(progress)}`
            : "분석 대기 중"}
        </div>
        <div className="bar">
          <span style={{ width: percent(progress) }} />
        </div>
        <p className="dim" style={{ fontSize: 12 }}>
          CPU로 대상을 따라가며 이동과 회전을 잽니다. 영상 1분에 수십 초에서 1분쯤 걸립니다. 그동안
          다른 클립을 손봐도 됩니다.
        </p>
      </>
    );
  }

  if (!analysis.ready) {
    return (
      <>
        {header}
        <p className="error-text">
          {analysis.status === "canceled"
            ? "분석을 취소했습니다."
            : `분석하지 못했습니다${analysis.error ? `: ${analysis.error}` : "."}`}
        </p>
        <button
          type="button"
          className="btn btn-primary btn-block"
          disabled={rerun.isPending}
          onClick={() => rerun.mutate(clip.id)}
        >
          다시 분석
        </button>
      </>
    );
  }

  return null;
}
