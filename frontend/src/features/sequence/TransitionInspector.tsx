import { mediaUrl } from "../../api/client";
import type { SequenceItem } from "../../api/types";
import inspector from "../../editor/Inspector.module.css";
import seg from "../segments/SegmentInspector.module.css";
import {
  fadeTransition,
  noneTransition,
  textCardTransition,
  type TextCardTransition,
  type TransitionAfter,
} from "../../types";
import type { SequenceEditor } from "./useSequenceEditor";
import s from "./TransitionInspector.module.css";

function gapTitle(editor: SequenceEditor): string {
  const gap = editor.selected;
  if (gap === "intro") {
    return "시작 제목";
  }
  if (gap === "outro") {
    return "끝 제목";
  }
  const items = editor.view?.items ?? [];
  const index = items.findIndex((item) => item.key === gap);
  const name = (item?: SequenceItem) =>
    item ? `${item.clip_position + 1}-${item.index + 1}` : "?";
  return `컷 ${name(items[index])} → ${name(items[index + 1])} 사이`;
}

function CardFields({
  card,
  onChange,
}: {
  card: TextCardTransition;
  onChange: (card: TextCardTransition) => void;
}) {
  return (
    <>
      <label className={seg.field}>
        <span className={seg.label}>문구 (줄바꿈 가능)</span>
        <textarea
          className={s.text}
          rows={2}
          value={card.text}
          maxLength={200}
          onChange={(event) => onChange({ ...card, text: event.target.value })}
        />
      </label>
      <div className={s.colors}>
        <label className={seg.field}>
          <span className={seg.label}>배경</span>
          <span className={s.color}>
            <input
              type="color"
              value={card.bg_color}
              onChange={(event) =>
                onChange({ ...card, bg_color: event.target.value.toUpperCase() })
              }
            />
            <span className="num">{card.bg_color}</span>
          </span>
        </label>
        <label className={seg.field}>
          <span className={seg.label}>글자</span>
          <span className={s.color}>
            <input
              type="color"
              value={card.font_color}
              onChange={(event) =>
                onChange({ ...card, font_color: event.target.value.toUpperCase() })
              }
            />
            <span className="num">{card.font_color}</span>
          </span>
        </label>
      </div>
      <label className={seg.field}>
        <span className={seg.row}>
          <span className={seg.label}>글자 크기</span>
          <span className="num">{card.font_size}</span>
        </span>
        <input
          type="range"
          min={24}
          max={160}
          step={4}
          value={card.font_size}
          onChange={(event) => onChange({ ...card, font_size: Number(event.target.value) })}
        />
      </label>
      <label className={seg.field}>
        <span className={seg.row}>
          <span className={seg.label}>표시 시간</span>
          <span className="num">{card.duration.toFixed(1)}초</span>
        </span>
        <input
          type="range"
          min={0.5}
          max={8}
          step={0.5}
          value={card.duration}
          onChange={(event) => onChange({ ...card, duration: Number(event.target.value) })}
        />
      </label>
    </>
  );
}

/** ④ 단계 오른쪽: 고른 컷 사이(또는 시작·끝 제목)의 전환. */
export function TransitionInspector({ editor }: { editor: SequenceEditor }) {
  const gap = editor.selected;
  if (!gap || !editor.settings) {
    return (
      <>
        <div>
          <div className={inspector.kicker}>전환·텍스트</div>
          <h2 className={inspector.heading}>컷 사이를 고르세요</h2>
        </div>
        <p className="notice">
          아래 결과 순서에서 컷 사이의 칩을 누르면 페이드나 텍스트 카드를 넣을 수 있습니다. 시작·끝
          제목도 같은 방식입니다.
        </p>
        <p className="dim" style={{ fontSize: 12 }}>
          기본 전환: {editor.settings ? editor.settings.default.type : "…"}
        </p>
      </>
    );
  }

  const title = gap === "intro" || gap === "outro";
  const current = editor.transitionOf(gap);
  const type = current?.type ?? "none";
  const set = (next: TransitionAfter | null) => editor.set(gap, next);
  const options: { type: TransitionAfter["type"] | "off"; label: string }[] = title
    ? [
        { type: "off", label: "없음" },
        { type: "text_card", label: "텍스트 카드" },
      ]
    : [
        { type: "none", label: "없음" },
        { type: "fade", label: "페이드" },
        { type: "text_card", label: "텍스트 카드" },
      ];

  function choose(next: TransitionAfter["type"] | "off") {
    if (next === "off") {
      set(null);
    } else if (next === "none") {
      set(noneTransition());
    } else if (next === "fade") {
      set(fadeTransition(current?.type === "fade" ? current.duration : undefined));
    } else {
      set(
        textCardTransition(
          current?.type === "text_card" ? current : { text: title ? "" : "다음 장면" },
        ),
      );
    }
  }

  return (
    <>
      <div>
        <div className={inspector.kicker}>{gapTitle(editor)}</div>
        <h2 className={inspector.heading}>{title ? "제목 카드" : "컷 사이 전환"}</h2>
      </div>
      <div className={seg.segmented} role="group" aria-label="전환 종류">
        {options.map((option) => (
          <button
            key={option.type}
            type="button"
            aria-pressed={
              option.type === "off" ? current == null : option.type === type && current != null
            }
            onClick={() => choose(option.type)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {current?.type === "fade" ? (
        <>
          <label className={seg.field}>
            <span className={seg.row}>
              <span className={seg.label}>길이</span>
              <span className="num">{current.duration.toFixed(1)}초</span>
            </span>
            <input
              type="range"
              min={0.2}
              max={2}
              step={0.1}
              value={current.duration}
              onChange={(event) => set(fadeTransition(Number(event.target.value)))}
            />
          </label>
          <p className="dim" style={{ fontSize: 12 }}>
            앞 컷 끝이 어두워지고 다음 컷이 밝아지며 시작합니다. 전체 길이는 변하지 않습니다.
          </p>
        </>
      ) : null}
      {current?.type === "text_card" ? <CardFields card={current} onChange={set} /> : null}
      {current?.type === "none" ? (
        <p className="muted">효과 없이 다음 컷으로 바로 넘어갑니다.</p>
      ) : null}
      {editor.error ? <p className="error-text">{editor.error}</p> : null}
      <div className={inspector.spacer} />
      {!title && current ? (
        <button type="button" className="btn btn-block" onClick={() => editor.applyToAll(current)}>
          모든 컷 사이에 적용
        </button>
      ) : null}
    </>
  );
}

/** ④ 단계 가운데: 고른 전환의 미리보기. 실제 렌더가 아니라 모양만 보여 준다. */
export function TransitionPreview({ editor }: { editor: SequenceEditor }) {
  const gap = editor.selected;
  const items = editor.view?.items ?? [];
  const index = items.findIndex((item) => item.key === gap);
  const before = gap === "outro" ? items.at(-1) : items[index];
  const after = gap === "intro" ? items[0] : items[index + 1];
  const current = gap ? editor.transitionOf(gap) : null;
  const frame = (item: SequenceItem | undefined, end: boolean) =>
    item
      ? mediaUrl.frame(item.video_id, end ? Math.max(item.start, item.end - 0.1) : item.start + 0.1)
      : null;

  if (current?.type === "text_card") {
    return (
      <div className={s.stage} style={{ background: current.bg_color }}>
        <span
          className={s.card}
          style={{ color: current.font_color, fontSize: `${(current.font_size / 1080) * 100}cqh` }}
        >
          {current.text || " "}
        </span>
        <span className={s.tag}>텍스트 카드 {current.duration.toFixed(1)}초 미리보기</span>
      </div>
    );
  }
  const left = frame(before, true);
  const right = frame(after, false);
  return (
    <div className={s.stage}>
      <div className={s.pair}>
        {left ? <img src={left} alt="앞 컷 끝" /> : <span />}
        {right ? <img src={right} alt="다음 컷 처음" /> : <span />}
      </div>
      {current?.type === "fade" ? <div className={s.fade} aria-hidden="true" /> : null}
      <span className={s.tag}>
        {!gap
          ? "컷 사이를 고르면 여기에 보입니다"
          : current?.type === "fade"
            ? `페이드 ${current.duration.toFixed(1)}초: 어두워졌다 밝아짐`
            : "바로 전환"}
      </span>
    </div>
  );
}
