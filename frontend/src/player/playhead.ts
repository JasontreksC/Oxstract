import { useSyncExternalStore } from "react";

/**
 * 뷰어 밖(타임라인)에서도 재생 위치를 읽게 하는 작은 저장소.
 * 재생 중 매 프레임 바뀌므로 편집기 전체를 다시 그리지 않도록 state 대신 쓴다.
 */
export interface Playhead {
  get: () => number;
  set: (time: number) => void;
  subscribe: (listener: () => void) => () => void;
}

export function createPlayhead(): Playhead {
  let time = 0;
  const listeners = new Set<() => void>();
  return {
    get: () => time,
    set: (next) => {
      if (next !== time) {
        time = next;
        listeners.forEach((listener) => listener());
      }
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export function usePlayhead(playhead: Playhead): number {
  return useSyncExternalStore(playhead.subscribe, playhead.get);
}
