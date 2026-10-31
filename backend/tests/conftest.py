"""Isolate MEDIA_ROOT per test so uploads never touch the repo."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.media import ffmpeg_bin, ffprobe_bin

HAS_FFMPEG = shutil.which(ffmpeg_bin()) is not None and shutil.which(ffprobe_bin()) is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg(ffmpeg, ffprobe)가 필요합니다")


@pytest.fixture(autouse=True)
def _isolated_media_root(tmp_path, monkeypatch):
    root = tmp_path / "media"
    monkeypatch.setenv("MEDIA_ROOT", str(root))
    return root


def make_video(
    path: Path,
    *,
    seconds: float = 2,
    size: str = "320x240",
    rate: int = 10,
    audio: bool = True,
    rotation: int | None = None,
) -> Path:
    """Write a small H.264 test clip with FFmpeg."""

    command = [ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi"]
    command += ["-i", f"testsrc=size={size}:rate={rate}:duration={seconds}"]
    if audio:
        command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        command += ["-c:a", "aac"]
    if rotation is None:
        subprocess.run([*command, str(path)], check=True)
        return path
    plain = path.with_name(f"plain-{path.name}")
    subprocess.run([*command, str(plain)], check=True)
    subprocess.run(
        [
            ffmpeg_bin(),
            "-v",
            "error",
            "-y",
            "-display_rotation",
            str(rotation),
            "-i",
            str(plain),
            "-c",
            "copy",
            str(path),
        ],
        check=True,
    )
    return path
