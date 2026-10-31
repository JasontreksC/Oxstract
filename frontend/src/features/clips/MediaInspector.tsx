import { useNavigate } from "react-router";
import { useRemoveClip, useRetryProxy } from "../../api/queries";
import { proxyReady, type Clip } from "../../api/types";
import { formatTime, percent } from "../../lib/format";
import s from "../../editor/Inspector.module.css";

function proxyLabel(clip: Clip): string {
  const proxy = clip.video.proxy;
  if (!proxy) {
    return "없음";
  }
  switch (proxy.status) {
    case "done":
      return "준비됨";
    case "running":
      return `만드는 중 ${percent(proxy.progress)}`;
    case "queued":
      return "대기 중";
    case "canceled":
      return "취소됨";
    default:
      return "실패";
  }
}

export interface MediaInspectorProps {
  projectId: string;
  clip: Clip | null;
}

export function MediaInspector({ projectId, clip }: MediaInspectorProps) {
  const navigate = useNavigate();
  const remove = useRemoveClip(projectId);
  const retry = useRetryProxy(projectId);

  if (!clip) {
    return (
      <>
        <div>
          <div className={s.kicker}>시작하기</div>
          <h2 className={s.heading}>영상 추가</h2>
        </div>
        <p className="notice">
          가운데에 영상을 끌어다 놓거나 왼쪽 아래 <strong>영상 추가</strong>를 누르세요. 여러 개를
          한 번에 올릴 수 있고, 목록 순서대로 하나의 결과 영상이 됩니다.
        </p>
      </>
    );
  }

  const { video } = clip;
  const failed = video.proxy?.status === "failed" || video.proxy?.status === "canceled";
  return (
    <>
      <div>
        <div className={s.kicker}>선택한 클립</div>
        <h2 className={s.heading} title={video.filename}>
          {video.filename}
        </h2>
      </div>
      <dl className={s.facts}>
        <dt>길이</dt>
        <dd className="num">{formatTime(video.duration)}</dd>
        <dt>해상도</dt>
        <dd className="num">
          {video.width}×{video.height}
          {video.height && video.width && video.height > video.width ? " 세로" : ""}
        </dd>
        <dt>프레임</dt>
        <dd className="num">
          {video.fps ? `${video.fps.toFixed(video.fps % 1 ? 2 : 0)}fps` : "알 수 없음"}
          {video.variable_fps ? " · 가변" : ""}
        </dd>
        <dt>코덱</dt>
        <dd>{video.video_codec?.toUpperCase() ?? "알 수 없음"}</dd>
        <dt>오디오</dt>
        <dd>{video.has_audio ? "있음" : "없음 (무음으로 이어 붙임)"}</dd>
        <dt>미리보기</dt>
        <dd>{proxyLabel(clip)}</dd>
      </dl>
      {failed ? (
        <div className={s.stack}>
          {video.proxy?.error ? <p className="error-text">{video.proxy.error}</p> : null}
          <button
            type="button"
            className="btn"
            disabled={retry.isPending}
            onClick={() => retry.mutate(video.id)}
          >
            미리보기 다시 만들기
          </button>
        </div>
      ) : null}
      <p className="notice">왼쪽 목록 순서가 결과 영상의 순서입니다. 끌어서 바꿀 수 있습니다.</p>
      <div className={s.spacer} />
      <button
        type="button"
        className="btn btn-primary btn-block"
        disabled={!proxyReady(video)}
        title={proxyReady(video) ? undefined : "미리보기가 준비되면 누를 수 있습니다."}
        onClick={() => navigate(`/p/${projectId}/target`)}
      >
        대상 지정으로
      </button>
      <button
        type="button"
        className="btn btn-danger btn-block"
        disabled={remove.isPending}
        onClick={() => {
          if (window.confirm(`${video.filename}을 프로젝트에서 뺄까요? 올린 파일도 지웁니다.`)) {
            remove.mutate(clip.id);
          }
        }}
      >
        클립 빼기
      </button>
      {remove.isError ? <p className="error-text">{remove.error.message}</p> : null}
    </>
  );
}
