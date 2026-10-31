import { useState } from "react";
import { Pencil } from "lucide-react";
import { useRenameProject } from "../api/queries";
import type { Project } from "../api/types";
import s from "./ProjectTitle.module.css";

/** 프로젝트 이름. 누르면 바로 고친다. Enter 저장, Esc 취소. */
export function ProjectTitle({ project }: { project: Project }) {
  const rename = useRenameProject(project.id);
  const [draft, setDraft] = useState<string | null>(null);

  function save() {
    const name = draft?.trim();
    setDraft(null);
    if (name && name !== project.name) {
      rename.mutate(name);
    }
  }

  return (
    <div className={s.title}>
      {draft == null ? (
        <button
          type="button"
          className={s.name}
          onClick={() => setDraft(project.name)}
          title="이름 바꾸기"
        >
          {rename.isPending ? rename.variables : project.name}
          <Pencil size={13} className="dim" aria-hidden="true" />
        </button>
      ) : (
        <input
          className={s.input}
          aria-label="프로젝트 이름"
          value={draft}
          maxLength={100}
          autoFocus
          onChange={(event) => setDraft(event.target.value)}
          onBlur={save}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              save();
            } else if (event.key === "Escape") {
              setDraft(null);
            }
          }}
        />
      )}
      <span className={s.sub}>
        클립 {project.clips.length}개{rename.isError ? " · 이름을 바꾸지 못했습니다" : ""}
      </span>
    </div>
  );
}
