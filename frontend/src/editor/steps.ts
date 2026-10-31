import { analysisReady, proxyReady, type Project } from "../api/types";

export const STEPS = [
  { id: "media", label: "영상" },
  { id: "target", label: "대상" },
  { id: "segments", label: "구간" },
  { id: "transitions", label: "전환·텍스트" },
  { id: "export", label: "내보내기" },
] as const;

export type StepId = (typeof STEPS)[number]["id"];

export function isStepId(value: string | undefined): value is StepId {
  return STEPS.some((step) => step.id === value);
}

/** 단계별로 열 수 없는 이유. 열 수 있으면 null. */
export function lockedReasons(project: Project): Record<StepId, string | null> {
  let target: string | null = null;
  if (project.clips.length === 0) {
    target = "영상을 먼저 추가하세요.";
  } else if (!project.clips.some((clip) => proxyReady(clip.video))) {
    target = "미리보기가 준비되면 열립니다.";
  }
  const segments = project.clips.some(analysisReady)
    ? null
    : "대상을 지정하고 분석이 끝난 클립이 있어야 열립니다.";
  const result = project.clips.some((clip) => clip.cuts && clip.cuts.length > 0)
    ? null
    : "남길 구간이 있는 클립이 있어야 열립니다.";
  return { media: null, target, segments, transitions: result, export: result };
}
