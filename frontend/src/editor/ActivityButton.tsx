import { useEffect, useRef, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useActiveJobs, useCancelJob } from "../api/queries";
import { percent } from "../lib/format";
import s from "./ActivityButton.module.css";

const KIND_LABEL: Record<string, string> = {
  proxy: "미리보기 만들기",
  analyze: "분석",
  render: "렌더",
};

/** 뒤에서 도는 작업 수. 누르면 목록과 취소 버튼이 열린다. */
export function ActivityButton() {
  const jobs = useActiveJobs();
  const cancel = useCancelJob();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const active = jobs.data ?? [];

  useEffect(() => {
    if (!open) {
      return;
    }
    function onDown(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={s.root} ref={root}>
      <button
        type="button"
        className="btn"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((value) => !value)}
      >
        {active.length ? (
          <LoaderCircle
            size={16}
            className="spin"
            color="var(--color-accent-strong)"
            aria-hidden="true"
          />
        ) : null}
        {active.length ? `작업 ${active.length}개 진행 중` : "진행 중인 작업 없음"}
      </button>
      {open ? (
        <div className={s.popover} role="dialog" aria-label="작업 목록">
          {active.length === 0 ? (
            <p className="muted">지금 도는 작업이 없습니다.</p>
          ) : (
            <ul className={s.list}>
              {active.map((job) => (
                <li key={job.id} className={s.job}>
                  <div className={s.row}>
                    <span>{KIND_LABEL[job.kind] ?? job.kind}</span>
                    <span className="muted num">
                      {job.status === "queued" ? "대기" : percent(job.progress)}
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      style={{ height: 28 }}
                      disabled={cancel.isPending}
                      onClick={() => cancel.mutate(job.id)}
                    >
                      취소
                    </button>
                  </div>
                  <div className="bar">
                    <span style={{ width: percent(job.progress) }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
