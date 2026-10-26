"""Rough detection-time estimates from plan section 10.

Per-frame numbers are the published YOLO11 figures (640px input). They do not
include decode, tracking interpolation, or re-encode. RTX 3060/4060 is quoted
from the plan as a range, not computed from the T4 table.
"""

from __future__ import annotations

FRAME_MS: dict[tuple[str, str], float] = {
    ("cpu", "n"): 56.0,
    ("cpu", "s"): 90.0,
    ("cpu", "m"): 183.0,
    ("t4", "n"): 1.5,
    ("t4", "s"): 2.5,
    ("t4", "m"): 4.7,
}

# Plan: about 2–5 minutes on an RTX 3060/4060 for the 10-minute example.
RTX_RANGE_MINUTES = (2.0, 5.0)


def estimate_detect_seconds(frames: int, model: str, device: str, sample_every: int = 1) -> float:
    """Return detection time in seconds for `frames` at the published ms/frame."""

    if frames < 0:
        raise ValueError("frames must be >= 0")
    if sample_every < 1:
        raise ValueError("sample_every must be >= 1")
    try:
        milliseconds = FRAME_MS[(device, model)]
    except KeyError as exc:
        raise KeyError(f"unknown device/model: {device}/{model}") from exc
    detected = (frames + sample_every - 1) // sample_every if frames else 0
    return detected * milliseconds / 1000.0


def ten_minute_1080p_frames(fps: int = 30) -> int:
    if fps < 1:
        raise ValueError("fps must be >= 1")
    return 10 * 60 * fps


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}분"


def main() -> None:
    frames = ten_minute_1080p_frames()
    print(f"10분 1080p 30fps 기준 프레임 수: {frames}")
    print("탐지 시간만 계산한다. 디코딩, 추적 보간, 재인코딩은 포함하지 않는다.")
    for model, label in (("n", "nano"), ("s", "small"), ("m", "medium")):
        cpu = estimate_detect_seconds(frames, model, "cpu")
        sampled = estimate_detect_seconds(frames, model, "cpu", sample_every=3)
        t4 = estimate_detect_seconds(frames, model, "t4")
        print(
            f"YOLO11 {label}: CPU {_minutes(cpu)}, "
            f"CPU 3프레임마다 {_minutes(sampled)} (하한), "
            f"T4 TensorRT {_minutes(t4)}"
        )
    low, high = RTX_RANGE_MINUTES
    print(f"RTX 3060/4060급 (계획서 참고 범위, 실측 아님): 약 {low:.0f}~{high:.0f}분")
    print("3프레임 간격의 CPU nano 계획서 범위는 추적 비용을 포함해 약 6~8분이다.")


if __name__ == "__main__":
    main()
