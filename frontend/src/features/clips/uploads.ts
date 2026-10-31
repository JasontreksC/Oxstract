import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { uploadClip } from "../../api/client";
import { keys } from "../../api/queries";

const VIDEO_EXTENSION = /\.(mp4|m4v|mov|mkv|webm|avi|mts|m2ts|3gp)$/i;

export function isVideoFile(file: File): boolean {
  return file.type.startsWith("video/") || VIDEO_EXTENSION.test(file.name);
}

/** 홈에서 새 프로젝트로 끌어 놓은 파일을 편집기가 이어받는다. */
const pending = new Map<string, File[]>();

export function setPendingFiles(projectId: string, files: File[]): void {
  pending.set(projectId, files);
}

export function takePendingFiles(projectId: string): File[] {
  const files = pending.get(projectId) ?? [];
  pending.delete(projectId);
  return files;
}

export interface UploadItem {
  id: string;
  name: string;
  size: number;
  progress: number;
  status: "waiting" | "uploading" | "error";
  error?: string;
}

export interface Uploads {
  items: UploadItem[];
  /** 영상이 아닌 파일은 거르고, 걸러진 개수를 돌려준다. */
  add: (files: Iterable<File>) => number;
  dismiss: (id: string) => void;
}

let uploadCounter = 0;

/** 한 번에 하나씩 차례로 올린다. 끝난 파일은 목록에서 빠지고 클립으로 나타난다. */
export function useUploads(projectId: string): Uploads {
  const client = useQueryClient();
  const [items, setItems] = useState<UploadItem[]>([]);
  const queue = useRef<{ id: string; file: File }[]>([]);
  const running = useRef(false);

  const update = useCallback((id: string, patch: Partial<UploadItem>) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }, []);

  const pump = useCallback(async () => {
    if (running.current) {
      return;
    }
    running.current = true;
    try {
      for (let next = queue.current.shift(); next; next = queue.current.shift()) {
        const { id, file } = next;
        update(id, { status: "uploading" });
        try {
          await uploadClip(projectId, file, (progress) => update(id, { progress }));
          await client.invalidateQueries({ queryKey: keys.project(projectId) });
          void client.invalidateQueries({ queryKey: keys.projects });
          setItems((current) => current.filter((item) => item.id !== id));
        } catch (error) {
          update(id, {
            status: "error",
            error: error instanceof Error ? error.message : "올리지 못했습니다.",
          });
        }
      }
    } finally {
      running.current = false;
    }
  }, [client, projectId, update]);

  const add = useCallback(
    (files: Iterable<File>) => {
      const all = Array.from(files);
      const videos = all.filter(isVideoFile);
      // crypto.randomUUID는 HTTPS에서만 있다. 사설망 http:// 접속에서도 돌도록 카운터를 쓴다.
      const added = videos.map((file) => ({ id: `upload-${++uploadCounter}`, file }));
      if (added.length) {
        queue.current.push(...added);
        setItems((current) => [
          ...current,
          ...added.map(({ id, file }) => ({
            id,
            name: file.name,
            size: file.size,
            progress: 0,
            status: "waiting" as const,
          })),
        ]);
        void pump();
      }
      return all.length - videos.length;
    },
    [pump],
  );

  const dismiss = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  return { items, add, dismiss };
}
