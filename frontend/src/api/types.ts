import type { TransitionAfter } from "../types";

/** /api 응답 모델. backend/app/schemas.py 와 같다. */

export type JobStatus = "queued" | "running" | "done" | "failed" | "canceled";

export interface Job {
  id: string;
  kind: string;
  ref_id: string;
  status: JobStatus;
  stage: string | null;
  progress: number;
  message: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ProxyState {
  status: JobStatus;
  progress: number;
  job_id: string;
  error: string | null;
}

export interface Video {
  id: string;
  filename: string;
  content_type: string | null;
  duration: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  rotation: number;
  video_codec: string | null;
  has_audio: boolean;
  variable_fps: boolean;
  /** 미리보기의 고정 fps. 프레임 번호 = floor(t × proxy_fps). */
  proxy_fps: number;
  proxy: ProxyState | null;
  created_at: string;
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type TargetSource = "drag" | "detect";

/** 클립이 따라갈 대상. 박스는 원본 픽셀(회전 적용 뒤)이다. */
export interface TargetInput {
  t: number;
  bbox: Box;
  source: TargetSource;
  class_name?: string | null;
  confidence?: number | null;
}

export interface Target extends TargetInput {
  frame_index: number;
}

export interface Detection {
  bbox: Box;
  class_name: string | null;
  confidence: number | null;
}

export interface DetectResult {
  t: number;
  frame_index: number;
  boxes: Detection[];
}

export interface AnalysisState {
  status: JobStatus;
  progress: number;
  stage: string | null;
  job_id: string;
  error: string | null;
  /** 신호 파일을 읽을 수 있다. */
  ready: boolean;
}

/** 분석 결과. 샘플마다 박스(원본 픽셀)와 움직임 신호. backend app/analysis.py */
export interface AnalysisResult {
  version: number;
  proxy_fps: number;
  sample_fps: number;
  target_frame: number;
  target_class: string | null;
  samples: {
    t: number[];
    x: (number | null)[];
    y: (number | null)[];
    w: (number | null)[];
    h: (number | null)[];
    visible: boolean[];
    /** 박스 대각선/초 */
    move: number[];
    /** 도/초 */
    turn: number[];
    /** 박스 대각선/초 */
    flow: number[];
  };
}

/** 남길 부분. 클립 안의 초. */
export interface Cut {
  start: number;
  end: number;
  score: number;
  /** 손으로 고친 범위가 닿았다. */
  edited: boolean;
}

export interface SegmentParams {
  sensitivity: number;
  use_move: boolean;
  /** 평면 회전과 박스 안 움직임(몸 돌리기, 제자리 회전). */
  use_turn: boolean;
  merge_gap: number;
  padding: number;
  min_length: number;
}

/** 자동 판정 위에 차례로 덧씌우는 손 편집. */
export interface SegmentEdit {
  op: "keep" | "drop";
  start: number;
  end: number;
}

export interface SegmentSettings {
  params: SegmentParams;
  edits: SegmentEdit[];
}

export interface SegmentsView extends SegmentSettings {
  cuts: Cut[];
  duration: number;
  kept: number;
}

export interface Clip {
  id: string;
  project_id: string;
  position: number;
  video: Video;
  target: Target | null;
  analysis: AnalysisState | null;
  /** 분석이 끝나면 생긴다. */
  cuts: Cut[] | null;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  clips: Clip[];
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  clip_count: number;
  total_duration: number;
  cover_video_id: string | null;
}

export function isActive(status: JobStatus | undefined): boolean {
  return status === "queued" || status === "running";
}

export function proxyReady(video: Video): boolean {
  return video.proxy?.status === "done";
}

export function analysisReady(clip: Clip): boolean {
  return clip.analysis?.ready ?? false;
}

export interface SequenceSettings {
  default: TransitionAfter;
  overrides: Record<string, TransitionAfter>;
  intro: TransitionAfter | null;
  outro: TransitionAfter | null;
}

export interface SequenceItem {
  key: string;
  clip_id: string;
  video_id: string;
  clip_position: number;
  index: number;
  start: number;
  end: number;
  transition_after: TransitionAfter | null;
}

export interface SequenceView extends SequenceSettings {
  items: SequenceItem[];
  total: number;
}

export interface RenderSettings {
  resolution: "source" | "1080" | "720";
  quality: "small" | "mid" | "high";
  audio: boolean;
}

export interface RenderView {
  id: string;
  project_id: string;
  settings: RenderSettings;
  created_at: string;
  status: JobStatus;
  progress: number;
  stage: string | null;
  error: string | null;
  ready: boolean;
  filename: string;
  duration: number | null;
  size_bytes: number | null;
}
