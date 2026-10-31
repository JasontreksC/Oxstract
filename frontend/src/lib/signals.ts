import type { AnalysisResult } from "../api/types";

export type SignalKey = "move" | "turn" | "flow";

export interface SignalInfo {
  key: SignalKey;
  label: string;
  unit: string;
  /** 그래프에서 이 값이 가운데 높이다. 구간 판정(M4)의 기본 기준 후보. */
  reference: number;
  color: string;
  help: string;
}

export const SIGNALS: SignalInfo[] = [
  {
    key: "move",
    label: "이동",
    unit: "대각선/초",
    reference: 0.25,
    color: "var(--color-signal-move)",
    help: "화면 안 위치와 크기 변화. 카메라 움직임은 뺀다",
  },
  {
    key: "turn",
    label: "회전",
    unit: "°/초",
    reference: 20,
    color: "var(--color-signal-rotate)",
    help: "화면 평면 안에서 도는 속도",
  },
  {
    key: "flow",
    label: "내부 움직임",
    unit: "대각선/초",
    reference: 0.1,
    color: "var(--color-signal-flow)",
    help: "제자리 회전, 몸 돌리기, 자세 변화",
  },
];

/** 시각 t에 가장 가까운 샘플 번호. 샘플 시각은 오름차순이다. */
export function sampleAt(result: AnalysisResult, t: number): number {
  const times = result.samples.t;
  let low = 0;
  let high = times.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (times[middle] < t) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  if (low > 0 && Math.abs(times[low - 1] - t) <= Math.abs(times[low] - t)) {
    return low - 1;
  }
  return low;
}

export function formatSignal(info: SignalInfo, value: number): string {
  return info.key === "turn" ? `${Math.round(value)}°/s` : value.toFixed(2);
}

/** 신호가 기준을 넘은 시간(초). 샘플 간격을 곱해 센다. */
export function secondsAbove(result: AnalysisResult, info: SignalInfo): number {
  const values = result.samples[info.key];
  const above = values.filter((value) => value >= info.reference).length;
  return above / result.sample_fps;
}
