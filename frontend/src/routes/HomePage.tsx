import { useRef, useState, type DragEvent } from "react";
import { Clapperboard, Film, Plus, Trash2, Upload } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { mediaUrl } from "../api/client";
import { useCreateProject, useDeleteProject, useProjects } from "../api/queries";
import type { ProjectSummary } from "../api/types";
import { isVideoFile, setPendingFiles } from "../features/clips/uploads";
import { formatDate, formatDuration } from "../lib/format";
import s from "./HomePage.module.css";

function defaultName(): string {
  const now = new Date();
  return `새 프로젝트 ${now.getMonth() + 1}월 ${now.getDate()}일`;
}

function hasFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer.types).includes("Files");
}

export function HomePage() {
  const projects = useProjects();
  const create = useCreateProject();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [dropping, setDropping] = useState(false);
  const dragDepth = useRef(0);

  async function start(files: File[] = []) {
    const project = await create.mutateAsync(defaultName());
    const videos = files.filter(isVideoFile);
    if (videos.length) {
      setPendingFiles(project.id, videos);
    }
    navigate(`/p/${project.id}/media`);
  }

  return (
    <div
      className={s.page}
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
          void start(Array.from(event.dataTransfer.files));
        }
      }}
    >
      <header className={s.header}>
        <div className={s.brand}>
          <Clapperboard size={20} aria-hidden="true" />
          Oxstract
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={create.isPending}
          onClick={() => void start()}
        >
          <Plus size={16} aria-hidden="true" />새 프로젝트
        </button>
      </header>

      <main className={s.main}>
        <h1 className={s.title}>프로젝트</h1>
        {create.isError ? <p className="error-text">{create.error.message}</p> : null}
        {projects.isPending ? (
          <p className="muted">불러오는 중…</p>
        ) : projects.isError ? (
          <p className="error-text">{projects.error.message}</p>
        ) : projects.data.length === 0 ? (
          <div className={s.empty}>
            <span className={s.emptyIcon}>
              <Upload size={26} aria-hidden="true" />
            </span>
            <p className={s.emptyTitle}>영상을 끌어다 놓으면 새 프로젝트가 시작됩니다</p>
            <p className="muted">
              지정한 물체가 움직이거나 도는 구간만 골라 여러 영상을 하나로 이어 붙입니다.
            </p>
            <button type="button" className="btn" onClick={() => input.current?.click()}>
              파일 고르기
            </button>
          </div>
        ) : (
          <ul className={s.grid}>
            {projects.data.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
            <li>
              <button
                type="button"
                className={s.newCard}
                disabled={create.isPending}
                onClick={() => void start()}
              >
                <Plus size={20} aria-hidden="true" />새 프로젝트
              </button>
            </li>
          </ul>
        )}
        <input
          ref={input}
          type="file"
          accept="video/*,.mkv,.mts,.m2ts"
          multiple
          hidden
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            void start(files);
          }}
        />
      </main>

      {dropping ? (
        <div className={s.dropOverlay} aria-hidden="true">
          <p>여기에 놓으면 새 프로젝트를 만듭니다</p>
        </div>
      ) : null}
    </div>
  );
}

function ProjectCard({ project }: { project: ProjectSummary }) {
  const remove = useDeleteProject();
  return (
    <li className={s.card}>
      <Link to={`/p/${project.id}/media`} className={s.cardLink}>
        <span className={s.cover}>
          {project.cover_video_id ? (
            <img src={mediaUrl.thumb(project.cover_video_id)} alt="" loading="lazy" />
          ) : (
            <Film size={28} className="dim" aria-hidden="true" />
          )}
        </span>
        <span className={s.cardBody}>
          <span className={s.cardName}>{project.name}</span>
          <span className="muted num">
            클립 {project.clip_count}
            {project.clip_count ? ` · 원본 ${formatDuration(project.total_duration)}` : ""}
          </span>
          <span className="dim">{formatDate(project.updated_at)}</span>
        </span>
      </Link>
      <button
        type="button"
        className={`btn icon-btn ${s.delete}`}
        aria-label={`${project.name} 삭제`}
        disabled={remove.isPending}
        onClick={() => {
          if (window.confirm(`"${project.name}"을 지울까요? 올린 영상도 함께 지웁니다.`)) {
            remove.mutate(project.id);
          }
        }}
      >
        <Trash2 size={16} aria-hidden="true" />
      </button>
    </li>
  );
}
