"""Render a project: the kept parts of every clip, in order, as one mp4.

Every piece is encoded to one output format first (size, 30 fps, H.264 yuv420p,
AAC 48 kHz stereo), so the pieces can then be joined with the concat demuxer
without re-encoding. Clips of a different shape are letterboxed; clips without
sound get silence so every piece has the same streams.

- A cut is cut from the original file with an accurate seek.
- A fade between two cuts fades the first one out to black and the next one in,
  inside the cuts themselves, so it does not change the length.
- A text card is its own piece: a solid colour with centred text (drawtext).

CPU only: libx264 software encoding.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.media import MediaError, ffmpeg_bin, run_ffmpeg

FPS = 30
RESOLUTIONS = {"1080": 1080, "720": 720}
QUALITY = {"small": ("veryfast", 26), "mid": ("medium", 22), "high": ("slow", 19)}
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
)


@dataclass(frozen=True)
class Card:
    """A solid-colour text scene. font_size is in pixels at 1080 lines."""

    text: str
    duration: float
    bg_color: str = "#111111"
    font_color: str = "#FFFFFF"
    font_size: float = 48


@dataclass(frozen=True)
class Piece:
    """A cut of a source file, or a card when `card` is set."""

    duration: float
    source: str | None = None
    start: float = 0.0
    has_audio: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    card: Card | None = None


@dataclass(frozen=True)
class Output:
    width: int
    height: int
    quality: str = "mid"
    audio: bool = True


@dataclass
class _Progress:
    total: float
    callback: Callable[[float], bool]
    done: float = 0.0
    log: list[str] = field(default_factory=list)

    def part(self, length: float) -> Callable[[float], bool]:
        def report(fraction: float) -> bool:
            return self.callback(min(0.99, (self.done + fraction * length) / self.total))

        return report


def output_size(resolution: str, first_width: int, first_height: int) -> tuple[int, int]:
    """Frame size: the first clip's shape, at its own size or scaled to 1080/720 lines."""

    portrait = first_height > first_width
    if resolution in RESOLUTIONS:
        short = RESOLUTIONS[resolution]
        long = round(short * 16 / 9)
        return (short, long) if portrait else (long, short)
    width, height = first_width, first_height
    scale = min(1.0, 3840 / max(width, height))
    return (round(width * scale / 2) * 2, round(height * scale / 2) * 2)


def find_font() -> str | None:
    configured = os.environ.get("FONT_FILE")
    if configured and Path(configured).is_file():
        return configured
    try:
        found = subprocess.run(
            ["fc-match", "-f", "%{file}", "Noto Sans CJK KR:bold"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        if found and Path(found).is_file():
            return found
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return next((path for path in FONT_CANDIDATES if Path(path).is_file()), None)


def _encode_args(output: Output) -> list[str]:
    preset, crf = QUALITY.get(output.quality, QUALITY["mid"])
    args = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
    args += ["-r", str(FPS), "-video_track_timescale", "15360"]
    if output.audio:
        args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
    return args


def _cut_command(piece: Piece, output: Output, dst: Path) -> list[str]:
    assert piece.source is not None
    w, h, d = output.width, output.height, piece.duration
    command = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-y"]
    command += ["-ss", f"{piece.start:.3f}", "-t", f"{d:.3f}", "-i", piece.source]
    silent = output.audio and not piece.has_audio
    if silent:
        command += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    video = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p"
    )
    audio = f"[{1 if silent else 0}:a]aresample=48000,aformat=channel_layouts=stereo"
    if piece.fade_in:
        video += f",fade=t=in:st=0:d={piece.fade_in:.3f}"
        audio += f",afade=t=in:st=0:d={piece.fade_in:.3f}"
    if piece.fade_out:
        start = max(0.0, d - piece.fade_out)
        video += f",fade=t=out:st={start:.3f}:d={piece.fade_out:.3f}"
        audio += f",afade=t=out:st={start:.3f}:d={piece.fade_out:.3f}"
    graph = video + "[v]"
    maps = ["-map", "[v]"]
    if output.audio:
        graph += f";{audio},atrim=0:{d:.3f}[a]"
        maps += ["-map", "[a]"]
    command += ["-filter_complex", graph, *maps, *_encode_args(output), "-t", f"{d:.3f}"]
    return [*command, "-progress", "pipe:1", "-nostats", str(dst)]


def _card_command(piece: Piece, output: Output, dst: Path, font: str, text_file: Path) -> list[str]:
    card = piece.card
    assert card is not None
    w, h, d = output.width, output.height, piece.duration
    size = max(8, round(card.font_size * h / 1080))
    command = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-y"]
    command += ["-f", "lavfi", "-i", f"color=c={card.bg_color}:s={w}x{h}:r={FPS}:d={d:.3f}"]
    if output.audio:
        command += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    draw = (
        f"drawtext=fontfile='{font}':textfile='{text_file}'"
        f":fontcolor={card.font_color}:fontsize={size}:line_spacing={size // 3}"
        ":x=(w-text_w)/2:y=(h-text_h)/2"
    )
    command += ["-vf", f"{draw},format=yuv420p", "-map", "0:v"]
    if output.audio:
        command += ["-map", "1:a"]
    command += [*_encode_args(output), "-t", f"{d:.3f}"]
    return [*command, "-progress", "pipe:1", "-nostats", str(dst)]


def render(
    pieces: list[Piece], output: Output, dst: Path, on_progress: Callable[[float], bool]
) -> float:
    """Encode the pieces and join them into `dst`. Return the result's length in seconds."""

    if not pieces:
        raise MediaError("남길 구간이 없습니다. 구간 단계에서 확인하세요.")
    font = find_font() if any(piece.card for piece in pieces) else None
    if any(piece.card for piece in pieces) and font is None:
        raise MediaError(
            "텍스트 카드용 글꼴이 없습니다. fonts-noto-cjk를 설치하거나 FONT_FILE을 지정하세요."
        )
    total = sum(piece.duration for piece in pieces)
    progress = _Progress(total=total, callback=on_progress)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as folder:
        work = Path(folder)
        names = []
        for index, piece in enumerate(pieces):
            part = work / f"{index:04d}.mp4"
            if piece.card is not None:
                assert font is not None
                text = work / f"{index:04d}.txt"
                text.write_text(piece.card.text or " ", encoding="utf-8")
                command = _card_command(piece, output, part, font, text)
            else:
                command = _cut_command(piece, output, part)
            run_ffmpeg(command, part, piece.duration, progress.part(piece.duration))
            progress.done += piece.duration
            names.append(part.name)
        listing = work / "pieces.txt"
        listing.write_text("".join(f"file '{name}'\n" for name in names), encoding="utf-8")
        joined = work / "joined.mp4"
        command = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-y"]
        command += ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy"]
        command += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(joined)]
        run_ffmpeg(command, joined, None, lambda fraction: True)
        shutil.move(joined, dst)
    on_progress(1.0)
    return total
