/** docs/design/style-guide.md 와 tokens.css 와 같은 값. 캔버스나 오버레이에서 쓴다. */

export const colors = {
  bg: "#0e1116",
  surface: "#151a21",
  surfaceCard: "#1a2028",
  surfaceRaised: "#1d232c",
  border: "#2a313c",
  borderStrong: "#333c49",
  text: "#e8edf4",
  textMuted: "#9aa6b8",
  textDim: "#8a95a7",
  accent: "#4c8dff",
  accentStrong: "#7aa7ff",
  onAccent: "#08111f",
  danger: "#f07178",
  success: "#6dcea0",
  warning: "#e6b35a",
  segment: "#4c8dff",
  signalMove: "#8fb4ff",
  signalRotate: "#c792ea",
  signalFlow: "#5cc8d6",
  threshold: "#e6b35a",
  transitionFade: "#c792ea",
  transitionText: "#e6b35a",
  overlay: "rgba(76, 141, 255, 0.16)",
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
  sans: '"Pretendard Variable", Pretendard, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif',
  mono: 'ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace',
} as const;
