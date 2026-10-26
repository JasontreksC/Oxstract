import type { TransitionAfter, TransitionType } from "../types";
import { fadeTransition, noneTransition, textCardTransition } from "../types";

export interface TransitionSettingsPanelProps {
  transition: TransitionAfter | null;
  disabled?: boolean;
  onChange?: (transition: TransitionAfter) => void;
}

const LABELS: Record<TransitionType, string> = {
  none: "효과 없음",
  fade: "페이드 인/아웃",
  text_card: "배경색 + 텍스트",
};

export function TransitionSettingsPanel({
  transition,
  disabled = false,
  onChange,
}: TransitionSettingsPanelProps) {
  const type = transition?.type ?? "none";

  function changeType(next: TransitionType) {
    if (next === "fade") {
      onChange?.(fadeTransition(transition?.type === "fade" ? transition.duration : undefined));
      return;
    }
    if (next === "text_card") {
      onChange?.(textCardTransition(transition?.type === "text_card" ? transition : undefined));
      return;
    }
    onChange?.(noneTransition());
  }

  return (
    <section className="panel stack" aria-label="전환 설정">
      <strong>컷 사이 전환</strong>
      <label className="field">
        종류
        <select
          value={type}
          disabled={disabled || transition == null}
          onChange={(event) => changeType(event.target.value as TransitionType)}
        >
          {(Object.keys(LABELS) as TransitionType[]).map((key) => (
            <option key={key} value={key}>
              {LABELS[key]}
            </option>
          ))}
        </select>
      </label>
      {transition?.type === "fade" ? (
        <label className="field">
          길이(초)
          <input
            type="number"
            min={0.1}
            step={0.1}
            disabled={disabled}
            value={transition.duration}
            onChange={(event) => onChange?.(fadeTransition(Number(event.target.value)))}
          />
        </label>
      ) : null}
      {transition?.type === "text_card" ? (
        <>
          <label className="field">
            표시 시간(초)
            <input
              type="number"
              min={0.1}
              step={0.1}
              disabled={disabled}
              value={transition.duration}
              onChange={(event) =>
                onChange?.(
                  textCardTransition({ ...transition, duration: Number(event.target.value) }),
                )
              }
            />
          </label>
          <label className="field">
            문구
            <input
              type="text"
              disabled={disabled}
              value={transition.text}
              onChange={(event) =>
                onChange?.(textCardTransition({ ...transition, text: event.target.value }))
              }
            />
          </label>
          <label className="field">
            배경색
            <input
              type="text"
              disabled={disabled}
              value={transition.bg_color}
              onChange={(event) =>
                onChange?.(textCardTransition({ ...transition, bg_color: event.target.value }))
              }
            />
          </label>
          <label className="field">
            글자색
            <input
              type="text"
              disabled={disabled}
              value={transition.font_color}
              onChange={(event) =>
                onChange?.(textCardTransition({ ...transition, font_color: event.target.value }))
              }
            />
          </label>
          <label className="field">
            글자 크기
            <input
              type="number"
              min={1}
              disabled={disabled}
              value={transition.font_size}
              onChange={(event) =>
                onChange?.(
                  textCardTransition({ ...transition, font_size: Number(event.target.value) }),
                )
              }
            />
          </label>
          <div
            className="preview-swatch"
            style={{ background: transition.bg_color, color: transition.font_color }}
          >
            {transition.text || "미리보기"}
          </div>
        </>
      ) : (
        <p className="muted">미리보기는 텍스트 카드일 때 배경과 문구만 보여 줍니다.</p>
      )}
    </section>
  );
}
