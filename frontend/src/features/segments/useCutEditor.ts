import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSaveSegments, useSegments } from "../../api/queries";
import type {
  Clip,
  Cut,
  SegmentEdit,
  SegmentParams,
  SegmentSettings,
  SegmentsView,
} from "../../api/types";
import { applyEdits, cutAt } from "../../lib/edits";

/** 슬라이더를 끄는 동안은 이만큼 쉬었을 때 한 번만 저장한다. */
const SAVE_DELAY = 120;
/** 이 시간 안에 이어진 설정 변경은 되돌리기 한 번으로 묶는다. */
const UNDO_GROUP = 700;

export interface CutEditor {
  ready: boolean;
  view: SegmentsView | undefined;
  settings: SegmentSettings | null;
  cuts: Cut[];
  saving: boolean;
  error: string | null;
  /** 고른 컷의 번호. 다시 잘라도 같은 자리의 컷을 가리키도록 시각으로 기억한다. */
  selected: number;
  select: (t: number | null) => void;
  setParams: (patch: Partial<SegmentParams>) => void;
  edit: (edits: SegmentEdit[]) => void;
  resetEdits: () => void;
  undo: () => void;
  canUndo: boolean;
}

export function useCutEditor(clip: Clip | null): CutEditor {
  const segments = useSegments(clip);
  const save = useSaveSegments(clip);
  const { mutate } = save;
  const clipId = clip?.id ?? null;
  const [draft, setDraft] = useState<{ clipId: string; settings: SegmentSettings } | null>(null);
  const [selectedAt, setSelectedAt] = useState<number | null>(null);
  const history = useRef<SegmentSettings[]>([]);
  const lastChange = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const [historySize, setHistorySize] = useState(0);

  useEffect(() => {
    history.current = [];
    setHistorySize(0);
    setSelectedAt(null);
    window.clearTimeout(timer.current);
  }, [clipId]);

  const server = segments.data;
  const settings = useMemo(
    () =>
      draft && draft.clipId === clipId
        ? draft.settings
        : server
          ? { params: server.params, edits: server.edits }
          : null,
    [draft, clipId, server],
  );

  const apply = useCallback(
    (next: SegmentSettings, delay: number, group: boolean) => {
      if (!clipId || !settings) {
        return;
      }
      const now = Date.now();
      if (!group || now - lastChange.current > UNDO_GROUP) {
        history.current = [...history.current.slice(-49), settings];
        setHistorySize(history.current.length);
      }
      lastChange.current = now;
      setDraft({ clipId, settings: next });
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => mutate(next), delay);
    },
    [clipId, settings, mutate],
  );

  const cuts = server?.cuts ?? [];
  return {
    ready: server != null,
    view: server,
    settings,
    cuts,
    saving: save.isPending,
    error: save.error?.message ?? segments.error?.message ?? null,
    selected: selectedAt == null ? -1 : cutAt(cuts, selectedAt),
    select: setSelectedAt,
    setParams: (patch) =>
      settings &&
      apply({ ...settings, params: { ...settings.params, ...patch } }, SAVE_DELAY, true),
    edit: (edits) =>
      settings &&
      edits.length &&
      apply({ ...settings, edits: applyEdits(settings.edits, edits) }, 0, false),
    resetEdits: () => settings && apply({ ...settings, edits: [] }, 0, false),
    undo: () => {
      const previous = history.current.pop();
      setHistorySize(history.current.length);
      if (previous && clipId) {
        lastChange.current = 0;
        setDraft({ clipId, settings: previous });
        window.clearTimeout(timer.current);
        mutate(previous);
      }
    },
    canUndo: historySize > 0,
  };
}
