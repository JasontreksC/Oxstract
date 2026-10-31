import { useRef, type ReactNode } from "react";
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Check, CircleAlert, Crosshair, GripVertical, LoaderCircle, Plus, X } from "lucide-react";
import { mediaUrl } from "../../api/client";
import { useReorderClips } from "../../api/queries";
import { locating, type Clip, type Project } from "../../api/types";
import { formatBytes, formatTime, percent } from "../../lib/format";
import type { Uploads } from "./uploads";
import s from "./ClipList.module.css";

export interface ClipListProps {
  project: Project;
  selectedId: string | null;
  onSelect: (clipId: string) => void;
  uploads: Uploads;
}

export function ClipList({ project, selectedId, onSelect, uploads }: ClipListProps) {
  const reorder = useReorderClips(project.id);
  const input = useRef<HTMLInputElement>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const ids = project.clips.map((clip) => clip.id);

  function onDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) {
      return;
    }
    const next = arrayMove(ids, ids.indexOf(String(active.id)), ids.indexOf(String(over.id)));
    reorder.mutate(next);
  }

  return (
    <aside className={`panel ${s.list}`} aria-label="클립">
      <div className={s.header}>
        <span className={s.heading}>클립 {project.clips.length}</span>
        {project.clips.length > 1 ? <span className="dim">끌어서 순서 변경</span> : null}
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          <ol className={s.clips}>
            {project.clips.map((clip, index) => (
              <SortableClip
                key={clip.id}
                clip={clip}
                order={index + 1}
                selected={clip.id === selectedId}
                onSelect={() => onSelect(clip.id)}
              />
            ))}
          </ol>
        </SortableContext>
      </DndContext>
      {uploads.items.length ? (
        <ul className={s.uploads} aria-label="올리는 중">
          {uploads.items.map((item) => (
            <li key={item.id} className={s.upload}>
              <div className={s.uploadRow}>
                <span className={s.name}>{item.name}</span>
                {item.status === "error" ? (
                  <button
                    type="button"
                    className="btn btn-ghost icon-btn"
                    aria-label={`${item.name} 오류 닫기`}
                    onClick={() => uploads.dismiss(item.id)}
                  >
                    <X size={14} aria-hidden="true" />
                  </button>
                ) : null}
              </div>
              {item.status === "error" ? (
                <span className="error-text">{item.error}</span>
              ) : (
                <>
                  <span className="dim num">
                    {formatBytes(item.size)} ·{" "}
                    {item.status === "waiting" ? "대기 중" : `올리는 중 ${percent(item.progress)}`}
                  </span>
                  <div className="bar">
                    <span style={{ width: percent(item.progress) }} />
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      ) : null}
      <button type="button" className={s.add} onClick={() => input.current?.click()}>
        <Plus size={16} aria-hidden="true" />
        영상 추가
      </button>
      <input
        ref={input}
        type="file"
        accept="video/*,.mkv,.mts,.m2ts"
        multiple
        hidden
        onChange={(event) => {
          if (event.target.files) {
            uploads.add(event.target.files);
          }
          event.target.value = "";
        }}
      />
    </aside>
  );
}

interface SortableClipProps {
  clip: Clip;
  order: number;
  selected: boolean;
  onSelect: () => void;
}

function SortableClip({ clip, order, selected, onSelect }: SortableClipProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: clip.id });
  const { video } = clip;
  return (
    <li
      ref={setNodeRef}
      className={s.clip}
      data-selected={selected || undefined}
      data-dragging={isDragging || undefined}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <button
        type="button"
        ref={setActivatorNodeRef}
        className={s.grip}
        aria-label={`${video.filename} 순서 옮기기`}
        {...attributes}
        {...listeners}
      >
        <GripVertical size={14} aria-hidden="true" />
      </button>
      <button type="button" className={s.select} onClick={onSelect} aria-pressed={selected}>
        <span className={`${s.order} dim num`}>{order}</span>
        <span className={s.thumb}>
          <img src={mediaUrl.thumb(video.id)} alt="" loading="lazy" />
        </span>
        <span className={s.meta}>
          <span className={s.name}>{video.filename}</span>
          <span className="muted num">{formatTime(video.duration)}</span>
          <ClipStatus clip={clip} />
        </span>
      </button>
    </li>
  );
}

function Badge({ tone, icon, children }: { tone: string; icon: ReactNode; children: ReactNode }) {
  return (
    <span className="badge num" style={{ color: `var(--color-${tone})` }}>
      {icon}
      {children}
    </span>
  );
}

const spinner = <LoaderCircle size={12} className="spin" aria-hidden="true" />;
const alert = <CircleAlert size={12} aria-hidden="true" />;

function ClipStatus({ clip }: { clip: Clip }) {
  const { proxy } = clip.video;
  const { analysis, target } = clip;
  if (proxy?.status === "failed" || proxy?.status === "canceled") {
    return (
      <Badge tone="danger" icon={alert}>
        미리보기 {proxy.status === "failed" ? "실패" : "취소됨"}
      </Badge>
    );
  }
  if (proxy && proxy.status !== "done") {
    return (
      <Badge tone="accent-strong" icon={spinner}>
        {proxy.status === "queued" ? "미리보기 대기" : `미리보기 ${percent(proxy.progress)}`}
      </Badge>
    );
  }
  if (locating(clip)) {
    return (
      <Badge tone="accent-strong" icon={spinner}>
        {analysis?.status === "queued"
          ? "대상 찾기 대기"
          : `대상 찾는 중 ${percent(analysis?.progress ?? 0)}`}
      </Badge>
    );
  }
  if (!target) {
    return (
      <Badge tone="warning" icon={<Crosshair size={12} aria-hidden="true" />}>
        {analysis?.status === "failed" ? "못 찾음 · 직접 지정" : "대상 필요"}
      </Badge>
    );
  }
  if (analysis?.status === "queued" || analysis?.status === "running") {
    return (
      <Badge tone="accent-strong" icon={spinner}>
        {analysis.status === "queued" ? "분석 대기" : `분석 ${percent(analysis.progress)}`}
      </Badge>
    );
  }
  if (analysis?.ready && clip.cuts) {
    const kept = clip.cuts.reduce((sum, cut) => sum + cut.end - cut.start, 0);
    return clip.cuts.length ? (
      <Badge tone="success" icon={<Check size={12} strokeWidth={3} aria-hidden="true" />}>
        컷 {clip.cuts.length}개 · {kept.toFixed(1)}초
      </Badge>
    ) : (
      <Badge tone="warning" icon={alert}>
        남는 구간 없음
      </Badge>
    );
  }
  return (
    <Badge tone="danger" icon={alert}>
      {analysis?.status === "canceled" ? "분석 취소됨" : "분석 실패"}
    </Badge>
  );
}
