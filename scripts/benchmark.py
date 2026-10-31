"""Measure the slow stages on this machine: proxy, analysis, render.

    python scripts/benchmark.py                      # synthetic 10-minute 1080p30 video
    python scripts/benchmark.py --minutes 2
    python scripts/benchmark.py clip.mp4 --box 800,380,330,330 --at 1.0 [--class dog]

Without a video it makes one: a textured disk that rests, moves, spins, leaves the
frame and comes back while the camera pans, looped to the wanted length, with a
tone for sound. Each stage runs in a fresh process, so the peak memory printed is
that stage's own (Python plus the FFmpeg it starts). Needs FFmpeg on PATH; run it
from the repository root with the backend's environment.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import resource
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SCENE_SECONDS = 30
SCENE_SIZE = (1920, 1080)
SCENE_FPS = 30
DISK = 330
#: Where the disk is at rest, top-left in source pixels; the target to pick.
SCENE_BOX = (800.0, 380.0, float(DISK), float(DISK))


def scene_state(t: float) -> tuple[float, float, float]:
    """(disk x, disk angle in degrees, camera pan) at `t` seconds into the 30 s scene."""

    t %= SCENE_SECONDS
    x, angle, pan = 800.0, 0.0, 0.0
    if 4 <= t < 8:
        x = 800 + 600 * (t - 4) / 4  # moves right
    elif 8 <= t < 12:
        x, angle = 1400, (t - 8) * 120  # spins in place
    elif 12 <= t < 14:
        x = 1400 + 700 * (t - 12) / 2  # leaves the frame
    elif 14 <= t < 18:
        x = 2200  # away
    elif 18 <= t < 20:
        x = 2200 - 1400 * (t - 18) / 2  # comes back
    if 22 <= t < 27:
        pan = 300 * (t - 22) / 5  # the camera pans
    elif t >= 27:
        pan = 300
    return x, angle, pan


def make_scene(path: Path, ffmpeg: str, size: tuple[int, int] = SCENE_SIZE) -> None:
    """Write the 30 s scene, scaled to `size`."""

    import cv2

    width, height = size
    k = width / SCENE_SIZE[0]
    rng = np.random.default_rng(3)
    margin = round(400 * k)
    noise = rng.integers(0, 255, (height + margin, width + margin), np.uint8)
    background = cv2.normalize(
        cv2.GaussianBlur(noise, (0, 0), 9 * k), None, 50, 170, cv2.NORM_MINMAX
    )
    background = cv2.cvtColor(background, cv2.COLOR_GRAY2BGR)
    side = max(8, round(DISK * k))
    grain = rng.integers(0, 255, (side, side), np.uint8)
    disk = cv2.normalize(cv2.GaussianBlur(grain, (0, 0), 2 * k), None, 0, 255, cv2.NORM_MINMAX)
    disk = cv2.merge([disk // 2, disk, np.clip(disk.astype(int) + 60, 0, 255).astype(np.uint8)])
    line = max(1, round(18 * k))
    cv2.line(disk, (side // 10, side // 2), (side - side // 10, side // 2), (255, 255, 255), line)
    cv2.circle(disk, (side // 3, side // 3), max(1, side // 11), (0, 0, 0), -1)
    mask = np.zeros((side, side), np.uint8)
    cv2.circle(mask, (side // 2, side // 2), side // 2 - 1, 255, -1)

    command = [ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24"]
    command += ["-s", f"{width}x{height}", "-r", str(SCENE_FPS), "-i", "-"]
    command += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]
    encoder = subprocess.Popen([*command, str(path)], stdin=subprocess.PIPE)
    assert encoder.stdin is not None
    for index in range(SCENE_SECONDS * SCENE_FPS):
        x, angle, pan = scene_state(index / SCENE_FPS)
        left = round(pan * k)
        frame = background[:height, left : left + width].copy()
        turn = cv2.getRotationMatrix2D((side / 2, side / 2), angle, 1)
        turned = cv2.warpAffine(disk, turn, (side, side))
        shape = cv2.warpAffine(mask, turn, (side, side)) > 0
        x0, y0 = round((x - pan) * k), round(SCENE_BOX[1] * k)
        a, b = max(0, x0), min(width, x0 + side)
        if b > a:
            region = frame[y0 : y0 + side, a:b]
            inside = shape[:, a - x0 : b - x0]
            region[inside] = turned[:, a - x0 : b - x0][inside]
        encoder.stdin.write(frame.tobytes())
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError("could not encode the scene")


def make_test_video(
    path: Path, seconds: float, ffmpeg: str, size: tuple[int, int] = SCENE_SIZE
) -> None:
    """The scene looped to `seconds`, with a tone as its sound."""

    with tempfile.TemporaryDirectory() as folder:
        scene = Path(folder) / "scene.mp4"
        make_scene(scene, ffmpeg, size)
        loops = max(0, int(np.ceil(seconds / SCENE_SECONDS)) - 1)
        command = [ffmpeg, "-v", "error", "-y", "-stream_loop", str(loops), "-i", str(scene)]
        command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
        command += ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k"]
        subprocess.run([*command, "-t", f"{seconds:.3f}", str(path)], check=True)


@dataclass(frozen=True)
class Measure:
    seconds: float
    memory_mb: float  # the stage's process plus its biggest FFmpeg, at their peaks
    note: str = ""


def _peak_mb() -> float:
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return (own + children) / 1024  # Linux reports KiB


def _timed(work: Callable[[], str]) -> Measure:
    start = time.perf_counter()
    note = work()
    return Measure(time.perf_counter() - start, _peak_mb(), note)


def stage_proxy(video: str, proxy: str) -> Measure:
    from app import media

    info = media.probe(video)

    def work() -> str:
        media.make_proxy(
            Path(video),
            Path(proxy),
            duration=info.duration,
            fps=info.fps,
            on_progress=lambda f: True,
        )
        return f"{info.width}x{info.height} → 720p"

    return _timed(work)


def stage_analysis(
    proxy: str,
    box: tuple[float, ...],
    at: float,
    size: tuple[int, int],
    class_name: str | None,
    out: str,
) -> Measure:
    import cv2

    from app import analysis, media
    from app.detect import get_detector

    capture = cv2.VideoCapture(proxy)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = round(capture.get(cv2.CAP_PROP_FPS))
    capture.release()
    detector = get_detector() if class_name else None

    def work() -> str:
        result = analysis.analyze(
            proxy,
            fps=fps,
            frame_count=frame_count,
            target_index=media.frame_index(at, fps),
            target_box=(box[0], box[1], box[2], box[3]),
            source_size=size,
            class_name=class_name,
            detector=detector,
            on_progress=lambda f: True,
        )
        Path(out).write_text(json.dumps(result), encoding="utf-8")
        visible = result["samples"]["visible"]
        kind = f"탐지 {class_name}" if class_name else "직접 그린 대상"
        return f"{kind}, 보임 {sum(visible)}/{len(visible)}"

    return _timed(work)


def stage_render(
    video: str, analysis_json: str, duration: float, quality: str, out: str
) -> Measure:
    from app import media, render, segments

    info = media.probe(video)
    cuts = segments.compute(
        json.loads(Path(analysis_json).read_text()), duration, segments.Params()
    )
    last = len(cuts) - 1
    pieces = [
        render.Piece(
            duration=cut.end - cut.start,
            source=video,
            start=cut.start,
            has_audio=info.has_audio,
            fade_in=0.5 if i else 0.0,
            fade_out=0.5 if i < last else 0.0,
        )
        for i, cut in enumerate(cuts)
    ]
    width, height = render.output_size("1080", info.width or 1920, info.height or 1080)
    output = render.Output(width, height, quality, True)

    def work() -> str:
        kept = render.render(pieces, output, Path(out), lambda f: True)
        megabytes = Path(out).stat().st_size / 1e6
        return f"1080p {quality}, 컷 {len(cuts)}개 {kept:.0f}초, {megabytes:.0f} MB"

    return _timed(work)


def _in_fresh_process(function: Callable[..., Measure], *args: object) -> Measure:
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=context) as pool:
        return pool.submit(function, *args).result()


def _row(name: str, measure: Measure, base: float | None) -> str:
    factor = f"{measure.seconds / base:.2f}배" if base else "-"
    memory = f"{measure.memory_mb:6.0f} MB"
    return f"{name:<14} {measure.seconds:8.1f}초  {factor:>7}  {memory}  {measure.note}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("video", nargs="?", help="measure this file instead of the synthetic one")
    parser.add_argument("--minutes", type=float, default=10.0, help="synthetic video length")
    parser.add_argument("--box", help="target x,y,w,h in source pixels (needed with a video)")
    parser.add_argument("--at", type=float, default=1.0, help="second where the box is")
    parser.add_argument("--class", dest="class_name", help="also analyse as a detected class")
    parser.add_argument("--quality", default="mid", choices=["small", "mid", "high"])
    parser.add_argument("--work", help="keep files here (default: a temporary folder)")
    args = parser.parse_args()

    from app import media

    ffmpeg = media.ffmpeg_bin()
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(args.work or temporary)
        work.mkdir(parents=True, exist_ok=True)
        if args.video:
            if not args.box:
                parser.error("--box is needed with a video")
            video = Path(args.video)
            box = tuple(float(v) for v in args.box.split(","))
        else:
            video = work / "benchmark.mp4"
            print(f"합성 영상 {args.minutes:g}분 만드는 중…", flush=True)
            make_test_video(video, args.minutes * 60, ffmpeg)
            box = SCENE_BOX
        info = media.probe(video)
        duration = info.duration or 0.0
        size = (info.width or 1, info.height or 1)
        proxy = str(work / "proxy.mp4")
        signals = str(work / "analysis.json")
        print(f"영상 {video.name}: {duration / 60:.1f}분, {size[0]}x{size[1]}, {info.fps:.2f}fps")
        print(f"{'단계':<14} {'시간':>9}  {'영상 대비':>7}  {'최대 메모리':>9}")

        measure = _in_fresh_process(stage_proxy, str(video), proxy)
        print(_row("미리보기", measure, duration), flush=True)
        measure = _in_fresh_process(stage_analysis, proxy, box, args.at, size, None, signals)
        print(_row("분석", measure, duration), flush=True)
        if args.class_name:
            other = str(work / "analysis-class.json")
            measure = _in_fresh_process(
                stage_analysis, proxy, box, args.at, size, args.class_name, other
            )
            print(_row("분석(탐지)", measure, duration), flush=True)
        out = str(work / "render.mp4")
        measure = _in_fresh_process(stage_render, str(video), signals, duration, args.quality, out)
        print(_row("렌더", measure, duration), flush=True)


if __name__ == "__main__":
    main()
