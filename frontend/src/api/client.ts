import type {
  AnalysisResult,
  Clip,
  DetectResult,
  Job,
  Project,
  ProjectSummary,
  RenderSettings,
  RenderView,
  SegmentSettings,
  SegmentsView,
  SequenceSettings,
  SequenceView,
  TargetInput,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailOf(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return `요청에 실패했습니다 (${status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "서버에 연결할 수 없습니다.");
  }
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detailOf(body, response.status));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const api = {
  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (name: string) => request<Project>("/projects", json("POST", { name })),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  renameProject: (id: string, name: string) =>
    request<Project>(`/projects/${id}`, json("PATCH", { name })),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  removeClip: (projectId: string, clipId: string) =>
    request<void>(`/projects/${projectId}/clips/${clipId}`, { method: "DELETE" }),
  reorderClips: (projectId: string, clipIds: string[]) =>
    request<Project>(`/projects/${projectId}/clips/order`, json("PUT", { clip_ids: clipIds })),
  retryProxy: (videoId: string) => request<Job>(`/videos/${videoId}/proxy`, { method: "POST" }),
  detect: (videoId: string, t: number) =>
    request<DetectResult>(`/videos/${videoId}/detect?t=${t.toFixed(4)}`, { method: "POST" }),
  setTarget: (projectId: string, clipId: string, target: TargetInput) =>
    request<Clip>(`/projects/${projectId}/clips/${clipId}/target`, json("PUT", target)),
  clearTarget: (projectId: string, clipId: string) =>
    request<Clip>(`/projects/${projectId}/clips/${clipId}/target`, { method: "DELETE" }),
  analysis: (projectId: string, clipId: string) =>
    request<AnalysisResult>(`/projects/${projectId}/clips/${clipId}/analysis`),
  rerunAnalysis: (projectId: string, clipId: string) =>
    request<Clip>(`/projects/${projectId}/clips/${clipId}/analysis`, { method: "POST" }),
  segments: (projectId: string, clipId: string) =>
    request<SegmentsView>(`/projects/${projectId}/clips/${clipId}/segments`),
  saveSegments: (projectId: string, clipId: string, settings: SegmentSettings) =>
    request<SegmentsView>(`/projects/${projectId}/clips/${clipId}/segments`, json("PUT", settings)),
  sequence: (projectId: string) => request<SequenceView>(`/projects/${projectId}/sequence`),
  saveSequence: (projectId: string, settings: SequenceSettings) =>
    request<SequenceView>(`/projects/${projectId}/sequence`, json("PUT", settings)),
  renders: (projectId: string) => request<RenderView[]>(`/projects/${projectId}/renders`),
  createRender: (projectId: string, settings: RenderSettings) =>
    request<RenderView>(`/projects/${projectId}/renders`, json("POST", settings)),
  deleteRender: (id: string) => request<void>(`/renders/${id}`, { method: "DELETE" }),
  activeJobs: () => request<Job[]>("/jobs?active=true"),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),
};

export const mediaUrl = {
  proxy: (videoId: string) => `/api/videos/${videoId}/proxy`,
  thumb: (videoId: string) => `/api/videos/${videoId}/thumb`,
  frame: (videoId: string, t: number) => `/api/videos/${videoId}/frame?t=${t.toFixed(4)}`,
  render: (id: string, download = false) =>
    `/api/renders/${id}/file${download ? "?download=true" : ""}`,
};

/** XHR로 올려야 업로드 진행률을 받을 수 있다. */
export function uploadClip(
  projectId: string,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<Clip> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/projects/${projectId}/clips`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded / event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as Clip);
      } else {
        reject(new ApiError(xhr.status, detailOf(xhr.response, xhr.status)));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "네트워크 오류로 올리지 못했습니다."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
