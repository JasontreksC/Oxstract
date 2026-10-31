"""Job worker: `python -m app.worker`.

Claims queued jobs one at a time from SQLite and runs them on the CPU: preview
proxies for new uploads, target analysis for clips, and project renders.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from collections.abc import Callable
from pathlib import Path

import cv2

from app import analysis, jobs, media, render, segments, sequence, store
from app.detect import DetectorUnavailable, get_detector

log = logging.getLogger("oxstract.worker")


class _Reporter:
    """Write progress at most every half second or every whole percent."""

    def __init__(self, job_id: str, stage: str) -> None:
        self.job_id = job_id
        self.stage = stage
        self.last_time = 0.0
        self.last_value = -1.0

    def __call__(self, fraction: float) -> bool:
        now = time.monotonic()
        if fraction - self.last_value < 0.01 and now - self.last_time < 0.5:
            return True
        self.last_time, self.last_value = now, fraction
        return jobs.report(self.job_id, fraction, self.stage)


def run_proxy(job: jobs.JobRecord) -> None:
    video = store.get_video(job.ref_id)
    if video is None:
        raise media.MediaError("영상이 삭제되었습니다.")
    directory = Path(video.path).parent
    partial = directory / "proxy.part.mp4"
    target = directory / "proxy.mp4"
    jobs.report(job.id, 0.0, "transcode", "미리보기 만드는 중")
    media.make_proxy(
        Path(video.path),
        partial,
        duration=video.duration,
        fps=video.fps,
        on_progress=_Reporter(job.id, "transcode"),
    )
    partial.replace(target)
    store.set_proxy_path(video.id, target)


def run_analysis(job: jobs.JobRecord) -> None:
    clip = store.get_clip_by_id(job.ref_id)
    if clip is None or clip.target is None:
        raise media.MediaError("클립이나 대상이 지워졌습니다.")
    video = clip.video
    proxy = video.proxy_path
    if not proxy or not Path(proxy).is_file():
        raise media.MediaError("미리보기가 아직 없습니다.")
    target = clip.target
    detector = None
    if target.get("class_name"):
        try:
            detector = get_detector()
        except DetectorUnavailable:
            log.warning("detector unavailable; tracking %s without re-detection", clip.id)
    fps = media.proxy_fps(video.fps)
    capture = cv2.VideoCapture(proxy)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    if frame_count <= 0:
        frame_count = round((video.duration or 0) * fps)
    jobs.report(job.id, 0.0, "track", "대상을 따라가는 중")
    bbox = target["bbox"]
    result = analysis.analyze(
        proxy,
        fps=fps,
        frame_count=frame_count,
        target_index=target["frame_index"],
        target_box=(bbox["x"], bbox["y"], bbox["width"], bbox["height"]),
        source_size=(video.width or 1, video.height or 1),
        class_name=target.get("class_name"),
        detector=detector,
        on_progress=_Reporter(job.id, "track"),
    )
    folder = store.clip_dir(clip.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"analysis-{job.id}.json"
    partial = path.with_suffix(".part")
    partial.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    partial.replace(path)
    # First cut with the clip's current settings, so it can be rendered without a visit.
    params, edits = segments.settings(clip.segment_params, clip.segment_edits)
    cuts = segments.as_json(segments.compute(result, video.duration, params, edits))
    if not store.set_analysis_result(clip.id, job.id, path, cuts):
        path.unlink(missing_ok=True)  # the target changed meanwhile; a newer job owns the clip


def run_render(job: jobs.JobRecord) -> None:
    record = store.get_render(job.ref_id)
    if record is None:
        raise media.MediaError("렌더 기록이 지워졌습니다.")
    project = store.get_project(record.project_id)
    if project is None:
        raise media.MediaError("프로젝트가 지워졌습니다.")
    settings = sequence.settings_of(project)
    pieces = sequence.pieces(project, settings)
    first = next((clip.video for clip in project.clips if clip.cuts), None)
    if first is None or not pieces:
        raise media.MediaError("남길 구간이 없습니다. 구간 단계에서 확인하세요.")
    options = record.settings
    width, height = render.output_size(
        options.get("resolution", "1080"), first.width or 1920, first.height or 1080
    )
    output = render.Output(
        width, height, options.get("quality", "mid"), bool(options.get("audio", True))
    )
    jobs.report(job.id, 0.0, "encode", "컷을 이어 붙이는 중")
    path = store.render_dir(record.id) / record.filename
    duration = render.render(pieces, output, path, _Reporter(job.id, "encode"))
    store.set_render_result(record.id, path, duration)


HANDLERS: dict[str, Callable[[jobs.JobRecord], None]] = {
    "proxy": run_proxy,
    "analyze": run_analysis,
    "render": run_render,
}


def run_once() -> bool:
    """Run the next queued job if there is one. Return whether a job ran."""

    job = jobs.claim_next()
    if job is None:
        return False
    handler = HANDLERS.get(job.kind)
    log.info("job %s (%s) started for %s", job.id, job.kind, job.ref_id)
    try:
        if handler is None:
            raise RuntimeError(f"알 수 없는 작업 종류: {job.kind}")
        handler(job)
    except media.Canceled:
        jobs.mark_canceled(job.id)
        log.info("job %s canceled", job.id)
    except Exception as exc:  # every failure is reported on the job
        jobs.fail(job.id, str(exc) or exc.__class__.__name__)
        log.exception("job %s failed", job.id)
    else:
        jobs.finish(job.id)
        log.info("job %s done", job.id)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    poll = float(os.environ.get("WORKER_POLL_SECONDS", "1"))
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    reset = jobs.recover_stale()
    if reset:
        log.warning("marked %d interrupted job(s) as failed", reset)
    log.info("worker ready (media root %s)", store.media_root().resolve())
    while not stopping:
        if not run_once():
            time.sleep(poll)


if __name__ == "__main__":
    main()
