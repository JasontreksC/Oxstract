"""Find the project's target in a clip where nobody pointed at it.

The user picks the object once, in one clip. Every other clip is scanned about
twice a second; on each scanned frame the candidates are the detector's boxes of
the same class (for a target picked from a detection box) and the spot where the
target's keypoints match. The candidate that looks most like the reference wins,
and becomes that clip's target frame and box.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import cv2

from app.analysis import ANALYSIS_LONG_SIDE
from app.appearance import Appearance
from app.detect import Detector
from app.media import Canceled, MediaError, frame_time

SCAN_SECONDS = 0.5
MAX_SCANS = 120
#: Weaker than this, the clip probably does not show the target.
ACCEPT = 0.65
#: Good enough to stop scanning early.
SURE = 0.92


@dataclass(frozen=True)
class Found:
    frame_index: int
    t: float
    box: tuple[float, float, float, float]  # source pixels
    score: float


def find_in_clip(
    path: str,
    *,
    fps: int,
    frame_count: int,
    source_size: tuple[int, int],
    reference: Appearance,
    class_name: str | None,
    detector: Detector | None,
    on_progress: Callable[[float], bool],
) -> Found | None:
    step = max(1, round(fps * SCAN_SECONDS))
    indices = list(range(step // 2, frame_count, step))
    if len(indices) > MAX_SCANS:
        stride = len(indices) / MAX_SCANS
        indices = [indices[int(i * stride)] for i in range(MAX_SCANS)]
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise MediaError("미리보기 파일을 열 수 없습니다.")
    best: tuple[float, int, tuple[float, float, float, float]] | None = None
    analysis_size = (1, 1)
    try:
        wanted = set(indices)
        last = indices[-1] if indices else -1
        current = 0
        while current <= last:
            if not capture.grab():
                break
            if current in wanted:
                ok, frame = capture.retrieve()
                if not ok:
                    break
                scale = min(1.0, ANALYSIS_LONG_SIDE / max(frame.shape[:2]))
                if scale < 1.0:
                    frame = cv2.resize(
                        frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                    )
                analysis_size = (frame.shape[1], frame.shape[0])
                candidates = []
                if detector is not None and class_name:
                    boxes = [
                        (d.x, d.y, d.width, d.height)
                        for d in detector(frame)
                        if d.class_name == class_name
                    ]
                    scored = reference.best(frame, boxes)
                    if scored is not None:
                        candidates.append(scored)
                located = reference.locate(frame)
                if located is not None:
                    candidates.append(located)
                for box, score in candidates:
                    if best is None or score > best[0]:
                        best = (score, current, box)
                position = indices.index(current) + 1
                if not on_progress(position / len(indices)):
                    raise Canceled
                if best is not None and best[0] >= SURE:
                    break
            current += 1
    finally:
        capture.release()
    if best is None or best[0] < ACCEPT:
        return None
    score, index, (x, y, w, h) = best
    # The analysis frame is the proxy scaled down, same shape as the source.
    fx, fy = source_size[0] / analysis_size[0], source_size[1] / analysis_size[1]
    box = (x * fx, y * fy, w * fx, h * fy)
    return Found(frame_index=index, t=frame_time(index, fps), box=box, score=round(score, 3))
