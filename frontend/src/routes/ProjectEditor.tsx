import { useEffect, useRef, useState, type DragEvent } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import {
  useAnalysis,
  useClearTarget,
  useProject,
  useRenders,
  useRetryProxy,
  useSetTarget,
} from "../api/queries";
import { analysisReady, proxyReady, type Clip, type Project } from "../api/types";
import { ActivityButton } from "../editor/ActivityButton";
import { ProjectTitle } from "../editor/ProjectTitle";
import { Stepper } from "../editor/Stepper";
import { isStepId, lockedReasons, type StepId } from "../editor/steps";
import { AnalysisInspector } from "../features/analysis/AnalysisInspector";
import { SegmentInspector } from "../features/segments/SegmentInspector";
import { SegmentTimeline } from "../features/segments/SegmentTimeline";
import { useCutEditor } from "../features/segments/useCutEditor";
import { TrackOverlay } from "../features/analysis/TrackOverlay";
import { ClipList } from "../features/clips/ClipList";
import { MediaInspector } from "../features/clips/MediaInspector";
import { ResultOrder } from "../features/clips/ResultOrder";
import { UploadDropzone } from "../features/clips/UploadDropzone";
import { takePendingFiles, useUploads } from "../features/clips/uploads";
import { ExportInspector, RenderPlayer } from "../features/export/ExportInspector";
import { Storyboard } from "../features/sequence/Storyboard";
import { TransitionInspector, TransitionPreview } from "../features/sequence/TransitionInspector";
import { useSequenceEditor } from "../features/sequence/useSequenceEditor";
import { TargetInspector } from "../features/target/TargetInspector";
import { TargetOverlay, type TargetDraft } from "../features/target/TargetOverlay";
import { createPlayhead } from "../player/playhead";
import { Viewer, type ViewerHandle } from "../player/Viewer";
import s from "./ProjectEditor.module.css";

function hasFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer.types).includes("Files");
}

function needsTarget(clip: Clip): boolean {
  return !clip.target && proxyReady(clip.video);
}

/** 고른 클립. 없으면 단계에 맞는 클립부터 연다(대상 단계는 대상이 필요한 것부터). */
function pickClip(project: Project | undefined, step: StepId, selectedId: string | null) {
  const clips = project?.clips ?? [];
  const fallback =
    step === "target"
      ? clips.find(needsTarget)
      : step === "segments"
        ? clips.find(analysisReady)
        : undefined;
  return clips.find((clip) => clip.id === selectedId) ?? fallback ?? clips[0] ?? null;
}

export function ProjectEditor() {
  const { projectId = "", step: stepParam } = useParams();
  const project = useProject(projectId);
  const navigate = useNavigate();
  const retry = useRetryProxy(projectId);
  const setTarget = useSetTarget(projectId);
  const clearTarget = useClearTarget(projectId);
  const uploads = useUploads(projectId);
  const { add } = uploads;
  const viewer = useRef<ViewerHandle>(null);
  const [playhead] = useState(createPlayhead);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ clipId: string; target: TargetDraft } | null>(null);
  const [dropping, setDropping] = useState(false);
  const dragDepth = useRef(0);

  const step: StepId = isStepId(stepParam) ? stepParam : "media";
  const selected = pickClip(project.data, step, selectedId);
  const analysis = useAnalysis(step === "segments" ? selected : null);
  const cutEditor = useCutEditor(step === "segments" ? selected : null);
  const sequencing = step === "transitions" || step === "export";
  const sequenceEditor = useSequenceEditor(projectId, project.data?.updated_at ?? "", sequencing);
  const renders = useRenders(projectId, step === "export");
  const [playingRender, setPlayingRender] = useState<string | null>(null);
  const [cutsOnly, setCutsOnly] = useState(false);

  useEffect(() => {
    const files = takePendingFiles(projectId);
    if (files.length) {
      add(files);
    }
  }, [projectId, add]);

  if (project.isPending) {
    return <p className={`${s.message} muted`}>불러오는 중…</p>;
  }
  if (project.isError) {
    return (
      <div className={s.message}>
        <p className="error-text">{project.error.message}</p>
        <Link to="/">프로젝트 목록으로</Link>
      </div>
    );
  }

  const data = project.data;
  const locked = lockedReasons(data);
  if (stepParam !== step || locked[step]) {
    return <Navigate to={`/p/${projectId}/media`} replace />;
  }
  const clipDraft = draft && selected && draft.clipId === selected.id ? draft.target : null;
  const targetProgress = {
    done: data.clips.filter((clip) => clip.target).length,
    total: data.clips.length,
  };

  function saveDraft() {
    if (!selected || !clipDraft) {
      return;
    }
    const current = selected.id;
    const { t, bbox, source, class_name, confidence } = clipDraft;
    setTarget.mutate(
      { clipId: current, target: { t, bbox, source, class_name, confidence } },
      {
        onSuccess: () => {
          setDraft(null);
          const next = data.clips.find((clip) => clip.id !== current && needsTarget(clip));
          if (next) {
            setSelectedId(next.id);
          }
        },
      },
    );
  }

  const targetError = setTarget.error?.message ?? clearTarget.error?.message ?? null;

  return (
    <div
      className={s.editor}
      onDragEnter={(event) => {
        if (hasFiles(event)) {
          dragDepth.current += 1;
          setDropping(true);
        }
      }}
      onDragOver={(event) => {
        if (hasFiles(event)) {
          event.preventDefault();
        }
      }}
      onDragLeave={(event) => {
        if (hasFiles(event)) {
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          setDropping(dragDepth.current > 0);
        }
      }}
      onDrop={(event) => {
        if (hasFiles(event)) {
          event.preventDefault();
          dragDepth.current = 0;
          setDropping(false);
          add(event.dataTransfer.files);
        }
      }}
    >
      <header className={s.topbar}>
        <div className={s.titleArea}>
          <Link to="/" className="btn icon-btn" aria-label="프로젝트 목록으로">
            <ArrowLeft size={18} aria-hidden="true" />
          </Link>
          <ProjectTitle project={data} />
        </div>
        <Stepper projectId={projectId} current={step} locked={locked} />
        <div className={s.activity}>
          <ActivityButton />
        </div>
      </header>

      <div className={s.body}>
        <ClipList
          project={data}
          selectedId={selected?.id ?? null}
          onSelect={setSelectedId}
          uploads={uploads}
        />
        <main className={s.center}>
          {step === "transitions" ? (
            <TransitionPreview editor={sequenceEditor} />
          ) : step === "export" ? (
            <RenderPlayer
              render={
                renders.data?.find((render) => render.id === playingRender && render.ready) ??
                renders.data?.find((render) => render.ready)
              }
            />
          ) : selected ? (
            <Viewer
              key={selected.video.id}
              ref={viewer}
              video={selected.video}
              initialTime={step === "target" ? selected.target?.t : undefined}
              playhead={playhead}
              playRanges={
                step === "segments" && cutsOnly
                  ? cutEditor.cuts.map((cut): [number, number] => [cut.start, cut.end])
                  : null
              }
              extraControls={
                step === "segments" && cutEditor.ready ? (
                  <div className={s.segmented} role="group" aria-label="재생 범위">
                    <button
                      type="button"
                      aria-pressed={!cutsOnly}
                      onClick={() => setCutsOnly(false)}
                    >
                      원본
                    </button>
                    <button
                      type="button"
                      aria-pressed={cutsOnly}
                      onClick={() => setCutsOnly(true)}
                      title="남는 구간만 이어서 재생합니다"
                    >
                      컷만
                    </button>
                  </div>
                ) : undefined
              }
              onRetryProxy={() => retry.mutate(selected.video.id)}
              overlay={
                step === "target"
                  ? (state) => (
                      <TargetOverlay
                        state={state}
                        video={selected.video}
                        saved={selected.target}
                        draft={clipDraft}
                        onPick={(target) => setDraft({ clipId: selected.id, target })}
                      />
                    )
                  : step === "segments" && analysis.data
                    ? (state) => (
                        <TrackOverlay state={state} video={selected.video} result={analysis.data} />
                      )
                    : undefined
              }
            />
          ) : (
            <UploadDropzone onFiles={add} />
          )}
        </main>
        <aside className={`panel ${s.inspector}`} aria-label="설정">
          <div className={s.inspectorBody}>
            {step === "transitions" ? (
              <TransitionInspector editor={sequenceEditor} />
            ) : step === "export" ? (
              <ExportInspector
                projectId={projectId}
                total={sequenceEditor.view?.total}
                renders={renders.data ?? []}
                playing={playingRender}
                onPlay={setPlayingRender}
              />
            ) : step === "segments" && selected ? (
              selected.analysis?.ready ? (
                <SegmentInspector
                  clip={selected}
                  result={analysis.data}
                  editor={cutEditor}
                  onSeek={(t) => viewer.current?.seek(t)}
                  onPlayCut={(start) => {
                    viewer.current?.seek(start);
                    viewer.current?.play();
                  }}
                />
              ) : (
                <AnalysisInspector clip={selected} />
              )
            ) : step === "target" && selected ? (
              <TargetInspector
                clip={selected}
                draft={clipDraft}
                progress={targetProgress}
                saving={setTarget.isPending || clearTarget.isPending}
                error={targetError}
                onSave={saveDraft}
                onDiscard={() => setDraft(null)}
                onSeek={(t) => viewer.current?.seek(t)}
                onClear={() => clearTarget.mutate(selected.id)}
              />
            ) : (
              <MediaInspector projectId={projectId} clip={selected} />
            )}
          </div>
        </aside>
      </div>

      <section className={`panel ${s.timeline}`} aria-label="타임라인">
        {sequencing ? (
          <Storyboard
            editor={{
              ...sequenceEditor,
              select: (gap) => {
                sequenceEditor.select(gap);
                if (step === "export") {
                  navigate(`/p/${projectId}/transitions`);
                }
              },
            }}
          />
        ) : step === "segments" && selected ? (
          analysis.data && cutEditor.ready ? (
            <SegmentTimeline
              title={selected.video.filename}
              result={analysis.data}
              duration={selected.video.duration ?? 0}
              editor={cutEditor}
              playhead={playhead}
              onSeek={(t) => viewer.current?.seek(t)}
            />
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              {selected.analysis?.ready
                ? "구간을 불러오는 중…"
                : "이 클립의 분석이 끝나면 여기에 이동·회전 그래프가 나타납니다."}
            </p>
          )
        ) : (
          <ResultOrder clips={data.clips} />
        )}
      </section>

      {dropping ? (
        <div className={s.dropOverlay} aria-hidden="true">
          <p>여기에 놓으면 클립으로 추가됩니다</p>
        </div>
      ) : null}
    </div>
  );
}
