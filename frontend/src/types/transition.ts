/**
 * 계획서 5.5 컷 사이 전환.
 * JSON Schema: schemas/transition.schema.json
 * 마지막 컷에는 두지 않는다.
 */

export type TransitionType = "fade" | "text_card" | "none";

export const DEFAULT_FADE_DURATION = 0.5;
export const DEFAULT_TEXT_CARD_DURATION = 2;

export interface FadeTransition {
  type: "fade";
  duration: number;
  bg_color?: null;
  text?: null;
  font_size?: null;
  font_color?: null;
}

export interface TextCardTransition {
  type: "text_card";
  duration: number;
  bg_color: string;
  text: string;
  font_size: number;
  font_color: string;
}

export interface NoneTransition {
  type: "none";
  duration?: null;
  bg_color?: null;
  text?: null;
  font_size?: null;
  font_color?: null;
}

export type TransitionAfter = FadeTransition | TextCardTransition | NoneTransition;

export function fadeTransition(duration = DEFAULT_FADE_DURATION): FadeTransition {
  return { type: "fade", duration };
}

export function textCardTransition(
  partial: Partial<Omit<TextCardTransition, "type">> = {},
): TextCardTransition {
  return {
    type: "text_card",
    duration: partial.duration ?? DEFAULT_TEXT_CARD_DURATION,
    bg_color: partial.bg_color ?? "#111111",
    text: partial.text ?? "",
    font_size: partial.font_size ?? 48,
    font_color: partial.font_color ?? "#FFFFFF",
  };
}

export function noneTransition(): NoneTransition {
  return { type: "none" };
}
