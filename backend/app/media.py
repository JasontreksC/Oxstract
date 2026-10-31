"""Probing, preview proxies, and frame extraction.

FFmpeg does the probing and transcoding (`FFPROBE_BIN`, `FFMPEG_BIN`, default from
PATH). OpenCV reads single frames for the selection screen and thumbnails.

Every uploaded video gets a proxy: H.264 + AAC, short side at most 720 px,
constant frame rate at most 30 fps, a keyframe every second, rotation already
applied. Browsers can play it (unlike many phone HEVC files), it seeks quickly,
and later analysis can decode it on CPU in reasonable time.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

PROXY_SHORT_SIDE = 720
PROXY_MAX_FPS = 30


class MediaError(ValueError):
    """Raised when a file is not a readable video or FFmpeg fails on it."""


class ToolMissing(RuntimeError):
    """Raised when ffmpeg or ffprobe is not installed."""


class Canceled(Exception):
    """Raised when a progress callback asks to stop."""


def ffmpeg_bin() -> str:
    return os.environ.get("FFMPEG_BIN") or "ffmpeg"


def ffprobe_bin() -> str:
    return os.environ.get("FFPROBE_BIN") or "ffprobe"


@dataclass(frozen=True)
class ProbeResult:
    duration: float | None
    width: int
    height: int
    fps: float | None
    rotation: int
    video_codec: str | None
    has_audio: bool
    variable_fps: bool


def _rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "0"):
        return None
    try:
        rate = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


def _rotation(stream: dict) -> int:
    angle = 0.0
    for item in stream.get("side_data_list") or []:
        if "rotation" in item:
            angle = float(item["rotation"])
            break
    else:
        rotate = (stream.get("tags") or {}).get("rotate")
        if rotate:
            angle = float(rotate)
    return int(round(angle / 90.0)) * 90 % 360


def _float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def probe(path: str | Path) -> ProbeResult:
    """Read stream metadata. Width and height are as displayed, after rotation."""

    command = [
        ffprobe_bin(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise ToolMissing("ffprobe를 찾을 수 없습니다. FFmpeg를 설치하세요.") from None
    except subprocess.TimeoutExpired:
        raise MediaError("영상 정보를 읽는 데 너무 오래 걸립니다.") from None
    if result.returncode != 0:
        raise MediaError("영상 파일을 해석할 수 없습니다.")
    info = json.loads(result.stdout or "{}")
    streams = info.get("streams") or []
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video"
            and not (s.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )
    if video is None or not video.get("width") or not video.get("height"):
        raise MediaError("영상 트랙이 없습니다.")

    rotation = _rotation(video)
    width, height = int(video["width"]), int(video["height"])
    if rotation in (90, 270):
        width, height = height, width
    avg = _rate(video.get("avg_frame_rate"))
    real = _rate(video.get("r_frame_rate"))
    duration = _float((info.get("format") or {}).get("duration")) or _float(video.get("duration"))
    return ProbeResult(
        duration=duration,
        width=width,
        height=height,
        fps=avg or real,
        rotation=rotation,
        video_codec=video.get("codec_name"),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        variable_fps=bool(avg and real and abs(avg - real) / real > 0.01),
    )


def proxy_fps(fps: float | None) -> int:
    if not fps:
        return PROXY_MAX_FPS
    return max(1, min(PROXY_MAX_FPS, round(fps)))


def proxy_command(src: Path, dst: Path, fps: int) -> list[str]:
    short = f"trunc(min({PROXY_SHORT_SIDE},{{}})/2)*2"
    scale = (
        f"scale=w='if(gte(iw,ih),-2,{short.format('iw')})'"
        f":h='if(gte(iw,ih),{short.format('ih')},-2)'"
    )
    return [
        ffmpeg_bin(),
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(src),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        f"{scale},fps={fps},format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-g",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(dst),
    ]


def run_ffmpeg(
    command: list[str], dst: Path, duration: float | None, on_progress: Callable[[float], bool]
) -> None:
    """Run an FFmpeg command that has `-progress pipe:1`, reporting progress of `duration`.

    `on_progress` gets a fraction in [0, 1] and returns False to stop, which kills
    FFmpeg, removes `dst`, and raises Canceled.
    """

    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True)
        except FileNotFoundError:
            raise ToolMissing("ffmpeg를 찾을 수 없습니다. FFmpeg를 설치하세요.") from None
        canceled = False
        assert process.stdout is not None
        for line in process.stdout:
            key, _, value = line.strip().partition("=")
            if key != "out_time_us" or not duration:
                continue
            try:
                fraction = int(value) / 1_000_000 / duration
            except ValueError:
                continue
            if not on_progress(min(1.0, max(0.0, fraction))):
                canceled = True
                process.kill()
                break
        process.wait()
        if canceled:
            dst.unlink(missing_ok=True)
            raise Canceled
        if process.returncode != 0:
            dst.unlink(missing_ok=True)
            errors.seek(0)
            lines = errors.read().decode(errors="replace").strip().splitlines()
            raise MediaError(lines[-1] if lines else f"ffmpeg 종료 코드 {process.returncode}")


def make_proxy(
    src: Path,
    dst: Path,
    *,
    duration: float | None,
    fps: float | None,
    on_progress: Callable[[float], bool],
) -> None:
    """Transcode `src` to the proxy format at `dst`."""

    run_ffmpeg(proxy_command(src, dst, proxy_fps(fps)), dst, duration, on_progress)


def frame_index(t: float, fps: int) -> int:
    """Index of the proxy frame shown at `t` seconds (constant frame rate)."""

    return max(0, math.floor(t * fps + 1e-6))


def frame_time(index: int, fps: int) -> float:
    """Middle of frame `index`, so browser seeks and server reads land on the same frame."""

    return (index + 0.5) / fps


def read_frame(path: str | Path, t: float, *, fps: int | None = None) -> np.ndarray:
    """Decode one frame as BGR.

    With `fps` (a constant-frame-rate proxy) the frame is found by index, which is
    exact. Without it OpenCV seeks by time, which can land one frame off.
    """

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise MediaError("영상 파일을 열 수 없습니다.")
    try:
        if fps:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index(t, fps))
        else:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise MediaError(f"t={t} 프레임을 읽을 수 없습니다.")
    return frame


def extract_frame_png(path: str | Path, t: float, *, fps: int | None = None) -> bytes:
    """Return the frame at `t` seconds as PNG bytes."""

    ok, buffer = cv2.imencode(".png", read_frame(path, t, fps=fps))
    if not ok:
        raise MediaError("PNG 인코딩에 실패했습니다.")
    return bytes(buffer.tobytes())


def write_thumbnail(path: str | Path, t: float, dst: Path, width: int = 320) -> None:
    """Save a small JPEG of the frame at `t`."""

    frame = read_frame(path, t)
    height = max(2, round(frame.shape[0] * width / frame.shape[1]))
    small = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise MediaError("JPEG 인코딩에 실패했습니다.")
    dst.write_bytes(buffer.tobytes())
