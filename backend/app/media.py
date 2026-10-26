"""Local media probing and frame extraction (M1).

OpenCV only, so the backend image needs no system FFmpeg yet.
FFmpeg joins in M4 for cuts and concat.
"""

from __future__ import annotations

import cv2


class MediaError(ValueError):
    """Raised when a stored file is not a readable video."""


def probe(path: str) -> tuple[float | None, int | None, int | None]:
    """Return (duration_seconds, width, height). Raise MediaError if unreadable."""

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise MediaError("영상 파일을 열 수 없습니다.")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frames / fps if fps > 0 and frames > 0 else None
        return duration, width or None, height or None
    finally:
        cap.release()


def extract_frame_png(path: str, t: float) -> bytes:
    """Return the frame nearest to `t` seconds as PNG bytes."""

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise MediaError("영상 파일을 열 수 없습니다.")
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise MediaError(f"t={t} 프레임을 읽을 수 없습니다.")
        ok, buf = cv2.imencode(".png", frame)
        if not ok:
            raise MediaError("PNG 인코딩에 실패했습니다.")
        return bytes(buf.tobytes())
    finally:
        cap.release()
