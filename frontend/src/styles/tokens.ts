/** docs/design/style-guide.md 와 tokens.css 와 같은 값. 캔버스나 오버레이에서 쓴다. */

export const colors = {
  bg: "#0f1218",
  surface: "#171c24",
  surfaceRaised: "#212833",
  border: "#313a49",
  text: "#e7edf6",
  textMuted: "#93a0b5",
  accent: "#4c8dff",
  accentStrong: "#80b0ff",
  danger: "#f07178",
  success: "#6dcea0",
  warning: "#e6b35a",
  segment: "#4c8dff",
  transitionFade: "#c792ea",
  transitionText: "#e6b35a",
  overlay: "rgba(76, 141, 255, 0.28)",
  overlayStroke: "#4c8dff",
} as const;

export const space = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 24,
  6: 32,
  8: 48,
} as const;

export const fontFamily = {
  sans: 'Pretendard, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif',
  mono: 'ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace',
} as const;
