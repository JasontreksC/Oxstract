import { useMemo, useRef, useState } from "react";
import { useSaveSequence, useSequence } from "../../api/queries";
import type { SequenceSettings, SequenceView } from "../../api/types";
import type { TransitionAfter } from "../../types";

/** "intro", "outro", 또는 그 뒤 전환을 고친 컷의 key. */
export type Gap = string;

export interface SequenceEditor {
  view: SequenceView | undefined;
  settings: SequenceSettings | null;
  selected: Gap | null;
  select: (gap: Gap | null) => void;
  transitionOf: (gap: Gap) => TransitionAfter | null;
  set: (gap: Gap, transition: TransitionAfter | null) => void;
  applyToAll: (transition: TransitionAfter) => void;
  saving: boolean;
  error: string | null;
}

const SAVE_DELAY = 300;

export function useSequenceEditor(projectId: string, version: string, enabled: boolean) {
  const query = useSequence(projectId, version, enabled);
  const save = useSaveSequence(projectId, version);
  const { mutate } = save;
  const [draft, setDraft] = useState<SequenceSettings | null>(null);
  const [selected, select] = useState<Gap | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const server = query.data;
  const settings = useMemo<SequenceSettings | null>(
    () =>
      draft ??
      (server
        ? {
            default: server.default,
            overrides: server.overrides,
            intro: server.intro,
            outro: server.outro,
          }
        : null),
    [draft, server],
  );

  function update(next: SequenceSettings) {
    setDraft(next);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => mutate(next), SAVE_DELAY);
  }

  // 화면에는 고친 값을 바로 보이도록, 서버 목록의 전환을 draft로 덮어 쓴다.
  const view = useMemo<SequenceView | undefined>(() => {
    if (!server || !settings) {
      return server;
    }
    const items = server.items.map((item, index) => ({
      ...item,
      transition_after:
        index === server.items.length - 1
          ? null
          : (settings.overrides[item.key] ?? settings.default),
    }));
    return { ...server, ...settings, items };
  }, [server, settings]);

  const editor: SequenceEditor = {
    view,
    settings,
    selected,
    select,
    transitionOf: (gap) => {
      if (!settings) {
        return null;
      }
      if (gap === "intro") {
        return settings.intro;
      }
      if (gap === "outro") {
        return settings.outro;
      }
      return settings.overrides[gap] ?? settings.default;
    },
    set: (gap, transition) => {
      if (!settings) {
        return;
      }
      if (gap === "intro" || gap === "outro") {
        update({ ...settings, [gap]: transition });
        return;
      }
      const overrides = { ...settings.overrides };
      if (transition) {
        overrides[gap] = transition;
      } else {
        delete overrides[gap];
      }
      update({ ...settings, overrides });
    },
    applyToAll: (transition) =>
      settings && update({ ...settings, default: transition, overrides: {} }),
    saving: save.isPending,
    error: save.error?.message ?? query.error?.message ?? null,
  };
  return editor;
}
