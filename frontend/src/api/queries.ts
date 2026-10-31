import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import {
  isActive,
  type Clip,
  type Project,
  type RenderSettings,
  type SegmentSettings,
  type SequenceSettings,
  type SegmentsView,
  type TargetInput,
} from "./types";

export const keys = {
  projects: ["projects"] as const,
  project: (id: string) => ["project", id] as const,
  activeJobs: ["jobs", "active"] as const,
  detect: (videoId: string, frame: number) => ["detect", videoId, frame] as const,
  analysis: (jobId: string) => ["analysis", jobId] as const,
  segments: (clipId: string, jobId: string) => ["segments", clipId, jobId] as const,
  sequence: (projectId: string) => ["sequence", projectId] as const,
  renders: (projectId: string) => ["renders", projectId] as const,
};

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: api.listProjects });
}

function hasPendingWork(project: Project | undefined): boolean {
  return (
    project?.clips.some(
      (clip) => isActive(clip.video.proxy?.status) || isActive(clip.analysis?.status),
    ) ?? false
  );
}

/** 미리보기나 분석이 도는 동안 1초마다 다시 읽는다. */
export function useProject(id: string) {
  return useQuery({
    queryKey: keys.project(id),
    queryFn: () => api.getProject(id),
    refetchInterval: (query) => (hasPendingWork(query.state.data) ? 1000 : false),
  });
}

export function useActiveJobs() {
  return useQuery({ queryKey: keys.activeJobs, queryFn: api.activeJobs, refetchInterval: 2000 });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createProject,
    onSuccess: (project) => {
      client.setQueryData(keys.project(project.id), project);
      void client.invalidateQueries({ queryKey: keys.projects });
    },
  });
}

export function useRenameProject(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.renameProject(id, name),
    onSuccess: (project) => {
      client.setQueryData(keys.project(id), project);
      void client.invalidateQueries({ queryKey: keys.projects });
    },
  });
}

export function useDeleteProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.projects }),
  });
}

export function useRemoveClip(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (clipId: string) => api.removeClip(projectId, clipId),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.project(projectId) });
      void client.invalidateQueries({ queryKey: keys.projects });
    },
  });
}

/** 순서는 화면에 먼저 반영하고, 실패하면 되돌린다. */
export function useReorderClips(projectId: string) {
  const client = useQueryClient();
  const key = keys.project(projectId);
  return useMutation({
    mutationFn: (clipIds: string[]) => api.reorderClips(projectId, clipIds),
    onMutate: async (clipIds) => {
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<Project>(key);
      if (previous) {
        const byId = new Map(previous.clips.map((clip) => [clip.id, clip]));
        const clips = clipIds.flatMap((id, position) => {
          const clip = byId.get(id);
          return clip ? [{ ...clip, position }] : [];
        });
        client.setQueryData<Project>(key, { ...previous, clips });
      }
      return { previous };
    },
    onError: (_error, _ids, context) => {
      if (context?.previous) {
        client.setQueryData(key, context.previous);
      }
    },
    onSuccess: (project) => client.setQueryData(key, project),
  });
}

export function useRetryProxy(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.retryProxy,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.project(projectId) }),
  });
}

export function useCancelJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.cancelJob,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.activeJobs });
      void client.invalidateQueries({ queryKey: ["project"] });
    },
  });
}

/** 한 프레임의 탐지 결과. 같은 프레임은 다시 묻지 않는다. */
export function useDetections(videoId: string, frame: number, t: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.detect(videoId, frame),
    queryFn: () => api.detect(videoId, t),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

function replaceClip(client: ReturnType<typeof useQueryClient>, projectId: string, clip: Clip) {
  client.setQueryData<Project>(keys.project(projectId), (project) =>
    project
      ? { ...project, clips: project.clips.map((c) => (c.id === clip.id ? clip : c)) }
      : project,
  );
}

export function useSetTarget(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ clipId, target }: { clipId: string; target: TargetInput }) =>
      api.setTarget(projectId, clipId, target),
    onSuccess: (clip) => replaceClip(client, projectId, clip),
  });
}

export function useClearTarget(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (clipId: string) => api.clearTarget(projectId, clipId),
    onSuccess: (clip) => replaceClip(client, projectId, clip),
  });
}

/** 끝난 분석의 신호. 분석 작업 id가 바뀌면(대상을 바꿈) 새로 읽는다. */
export function useAnalysis(clip: Clip | null) {
  const jobId = clip?.analysis?.ready ? clip.analysis.job_id : null;
  const projectId = clip?.project_id ?? "";
  const clipId = clip?.id ?? "";
  return useQuery({
    queryKey: keys.analysis(jobId ?? "none"),
    queryFn: () => api.analysis(projectId, clipId),
    enabled: jobId != null,
    staleTime: Infinity,
  });
}

export function useRerunAnalysis(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (clipId: string) => api.rerunAnalysis(projectId, clipId),
    onSuccess: (clip) => replaceClip(client, projectId, clip),
  });
}

/** 클립을 어떻게 자르는지(설정, 손 편집, 결과). 분석이 바뀌면 새로 읽는다. */
export function useSegments(clip: Clip | null) {
  const jobId = clip?.analysis?.ready ? clip.analysis.job_id : null;
  const projectId = clip?.project_id ?? "";
  const clipId = clip?.id ?? "";
  return useQuery({
    queryKey: keys.segments(clipId, jobId ?? "none"),
    queryFn: () => api.segments(projectId, clipId),
    enabled: jobId != null,
    staleTime: Infinity,
  });
}

/** 다시 자르기. 결과는 구간 쿼리와 프로젝트의 클립 둘 다에 반영한다. */
export function useSaveSegments(clip: Clip | null) {
  const client = useQueryClient();
  const jobId = clip?.analysis?.job_id ?? "none";
  const projectId = clip?.project_id ?? "";
  const clipId = clip?.id ?? "";
  return useMutation({
    mutationFn: (settings: SegmentSettings) => api.saveSegments(projectId, clipId, settings),
    onSuccess: (view: SegmentsView) => {
      client.setQueryData(keys.segments(clipId, jobId), view);
      client.setQueryData<Project>(keys.project(projectId), (project) =>
        project
          ? {
              ...project,
              clips: project.clips.map((c) => (c.id === clipId ? { ...c, cuts: view.cuts } : c)),
            }
          : project,
      );
    },
  });
}

/** 결과 순서와 전환. 구간이 바뀌면(프로젝트 갱신 시각) 다시 읽는다. */
export function useSequence(projectId: string, version: string, enabled: boolean) {
  return useQuery({
    queryKey: [...keys.sequence(projectId), version],
    queryFn: () => api.sequence(projectId),
    enabled,
  });
}

export function useSaveSequence(projectId: string, version: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (settings: SequenceSettings) => api.saveSequence(projectId, settings),
    onSuccess: (view) => client.setQueryData([...keys.sequence(projectId), version], view),
  });
}

export function useRenders(projectId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.renders(projectId),
    queryFn: () => api.renders(projectId),
    enabled,
    refetchInterval: (query) =>
      query.state.data?.some((render) => isActive(render.status)) ? 1000 : false,
  });
}

export function useCreateRender(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (settings: RenderSettings) => api.createRender(projectId, settings),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.renders(projectId) }),
  });
}

export function useDeleteRender(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteRender,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.renders(projectId) }),
  });
}
