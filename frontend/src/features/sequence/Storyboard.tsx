import { Plus } from "lucide-react";
import { mediaUrl } from "../../api/client";
import type { SequenceItem } from "../../api/types";
import { formatTime } from "../../lib/format";
import type { TransitionAfter } from "../../types";
import type { SequenceEditor } from "./useSequenceEditor";
import s from "./Storyboard.module.css";

export function transitionLabel(transition: TransitionAfter | null): string {
  if (!transition || transition.type === "none") {
    return "없음";
  }
  if (transition.type === "fade") {
    return `페이드 ${transition.duration.toFixed(1)}초`;
  }
  return `텍스트 ${transition.duration.toFixed(1)}초`;
}

const COLOR = {
  none: "var(--color-text-dim)",
  fade: "var(--color-transition-fade)",
  text_card: "var(--color-transition-text)",
};

function CutCard({ item }: { item: SequenceItem }) {
  const thumb = Math.min(item.end - 0.05, item.start + 0.2);
  return (
    <div className={s.card}>
      <div className={s.thumb}>
        <img src={mediaUrl.frame(item.video_id, thumb)} alt="" loading="lazy" />
        <span className={s.label}>
          {item.clip_position + 1}-{item.index + 1}
        </span>
      </div>
      <div className="num">{(item.end - item.start).toFixed(1)}초</div>
      <div className="dim num" style={{ fontSize: 11 }}>
        {formatTime(item.start)}–{formatTime(item.end)}
      </div>
    </div>
  );
}

function TitleSlot({
  gap,
  label,
  editor,
}: {
  gap: "intro" | "outro";
  label: string;
  editor: SequenceEditor;
}) {
  const card = editor.transitionOf(gap);
  return (
    <button
      type="button"
      className={card ? s.title : s.addTitle}
      data-selected={editor.selected === gap || undefined}
      style={
        card
          ? { background: card.bg_color ?? undefined, color: card.font_color ?? undefined }
          : undefined
      }
      onClick={() => editor.select(gap)}
    >
      {card ? (
        <span className={s.titleText}>{card.text || label}</span>
      ) : (
        <>
          <Plus size={14} aria-hidden="true" />
          {label}
        </>
      )}
    </button>
  );
}

/** ④ 단계 아래: 결과 순서대로 늘어선 컷과 그 사이의 전환 칩. */
export function Storyboard({ editor }: { editor: SequenceEditor }) {
  const view = editor.view;
  if (!view) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        결과 순서를 불러오는 중…
      </p>
    );
  }
  const items = view.items;
  return (
    <>
      <div className={s.header}>
        <span className={s.heading}>결과 순서</span>
        <span className="muted num">
          컷 {items.length}개 · 총 {view.total.toFixed(1)}초
        </span>
        <span className={`${s.hint} dim`}>컷 사이 칩을 눌러 전환을 바꾸세요</span>
      </div>
      <div className={s.strip}>
        <TitleSlot gap="intro" label="시작 제목" editor={editor} />
        {items.map((item, i) => {
          const next = items[i + 1];
          const transition = item.transition_after;
          return (
            <div key={item.key} className={s.group}>
              <CutCard item={item} />
              {next ? (
                <>
                  <button
                    type="button"
                    className={s.chip}
                    data-selected={editor.selected === item.key || undefined}
                    aria-label={`${item.clip_position + 1}-${item.index + 1} 다음 전환: ${transitionLabel(transition)}`}
                    onClick={() => editor.select(item.key)}
                  >
                    <span
                      className={s.dot}
                      style={{ background: COLOR[transition?.type ?? "none"] }}
                    />
                    {transitionLabel(transition)}
                  </button>
                  {next.clip_id !== item.clip_id ? (
                    <span className={s.boundary} aria-hidden="true" />
                  ) : null}
                </>
              ) : null}
            </div>
          );
        })}
        <TitleSlot gap="outro" label="끝 제목" editor={editor} />
      </div>
    </>
  );
}
