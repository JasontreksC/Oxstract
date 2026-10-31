"""Turn analysis signals into the parts of a clip to keep.

Cheap enough (milliseconds) to rerun on every slider change, so the server is the
only place it happens: the editor asks for a recount, and rendering uses the same
stored result.

1. Activity per sample: each enabled signal divided by its threshold (thresholds
   shrink as sensitivity grows), the largest one wins, zero where the target is
   not visible, then a short moving average.
2. Hysteresis: a part starts where activity reaches 1 and ends once it falls
   below EXIT_RATIO, so it does not flicker around the threshold.
3. Short pauses are merged, parts shorter than min_length dropped, and padding
   added on both sides.
4. Manual edits are applied last, in order: "keep" adds a range, "drop" removes
   one. They are plain time ranges, so they keep meaning the same thing when the
   automatic parts move with a new sensitivity.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

#: Signal values at sensitivity 1 that count as motion. Units as in app/analysis.py.
THRESHOLDS = {"move": 0.25, "turn": 20.0, "flow": 0.1}
EXIT_RATIO = 0.7
SMOOTH_SECONDS = 0.3
MIN_PIECE = 0.1


@dataclass(frozen=True)
class Params:
    sensitivity: float = 1.0
    use_move: bool = True
    #: In-plane rotation and motion inside the box (turning around, spinning in place).
    use_turn: bool = True
    merge_gap: float = 0.5
    padding: float = 0.3
    min_length: float = 1.0


@dataclass(frozen=True)
class Edit:
    op: str  # "keep" | "drop"
    start: float
    end: float


@dataclass(frozen=True)
class Cut:
    start: float
    end: float
    score: float
    edited: bool


def activity(samples: dict, sample_fps: float, params: Params) -> np.ndarray:
    """Per-sample motion relative to the threshold: 1 means exactly at it."""

    count = len(samples["t"])
    parts = []
    if params.use_move:
        parts.append(np.asarray(samples["move"], float) / THRESHOLDS["move"])
    if params.use_turn:
        parts.append(np.asarray(samples["turn"], float) / THRESHOLDS["turn"])
        parts.append(np.asarray(samples["flow"], float) / THRESHOLDS["flow"])
    if not parts or count == 0:
        return np.zeros(count)
    level = np.max(parts, axis=0) * params.sensitivity
    level[~np.asarray(samples["visible"], bool)] = 0.0
    window = max(1, round(SMOOTH_SECONDS * sample_fps))
    if window > 1:
        padded = np.pad(level, (window // 2, window - 1 - window // 2), mode="edge")
        level = np.convolve(padded, np.ones(window) / window, mode="valid")
    return level


def _merge(ranges: Iterable[tuple[float, float]], gap: float = 0.0) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(ranges):
        if merged and start - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def automatic(
    times: np.ndarray, level: np.ndarray, sample_fps: float, duration: float, params: Params
) -> list[tuple[float, float]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(level):
        if start is None and value >= 1.0:
            start = index
        elif start is not None and value < EXIT_RATIO:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(level) - 1))

    half = 0.5 / sample_fps
    ranges = _merge(((times[a] - half, times[b] + half) for a, b in runs), params.merge_gap)
    ranges = [(a, b) for a, b in ranges if b - a >= params.min_length]
    padded = ((max(0.0, a - params.padding), min(duration, b + params.padding)) for a, b in ranges)
    return _merge(padded)


def _subtract(
    ranges: list[tuple[float, float, bool]], start: float, end: float
) -> list[tuple[float, float, bool]]:
    result = []
    for a, b, edited in ranges:
        if b <= start or a >= end:
            result.append((a, b, edited))
            continue
        if a < start:
            result.append((a, start, True))
        if b > end:
            result.append((end, b, True))
    return result


def _add(
    ranges: list[tuple[float, float, bool]], start: float, end: float
) -> list[tuple[float, float, bool]]:
    merged: list[tuple[float, float, bool]] = []
    for a, b, edited in sorted([*ranges, (start, end, True)]):
        if merged and a <= merged[-1][1]:
            prev_a, prev_b, prev_edited = merged[-1]
            merged[-1] = (prev_a, max(prev_b, b), prev_edited or edited)
        else:
            merged.append((a, b, edited))
    return merged


def apply_edits(
    ranges: list[tuple[float, float]], edits: Iterable[Edit], duration: float
) -> list[tuple[float, float, bool]]:
    current = [(a, b, False) for a, b in ranges]
    for edit in edits:
        start, end = max(0.0, edit.start), min(duration, edit.end)
        if end <= start:
            continue
        current = _add(current, start, end) if edit.op == "keep" else _subtract(current, start, end)
    return [(a, b, edited) for a, b, edited in current if b - a >= MIN_PIECE]


def compute(
    analysis: dict, duration: float | None, params: Params, edits: Iterable[Edit] = ()
) -> list[Cut]:
    """The parts to keep, in time order, from an analysis result (app/analysis.py)."""

    samples = analysis["samples"]
    sample_fps = float(analysis["sample_fps"])
    times = np.asarray(samples["t"], float)
    if not len(times):
        return []
    end = duration or float(times[-1] + 0.5 / sample_fps)
    level = activity(samples, sample_fps, params)
    ranges = apply_edits(automatic(times, level, sample_fps, end, params), edits, end)

    cuts = []
    for start, stop, edited in ranges:
        inside = level[(times >= start) & (times <= stop)]
        score = float(np.clip(inside.mean() / 3, 0, 1)) if len(inside) else 0.0
        cuts.append(Cut(round(start, 3), round(stop, 3), round(score, 3), edited))
    return cuts


def settings(params: dict | None, edits: list | None) -> tuple[Params, list[Edit]]:
    """Stored JSON (or nothing yet) to Params and Edits."""

    return Params(**(params or {})), [Edit(**edit) for edit in (edits or [])]


def as_json(cuts: list[Cut]) -> list[dict]:
    return [{"start": c.start, "end": c.end, "score": c.score, "edited": c.edited} for c in cuts]
