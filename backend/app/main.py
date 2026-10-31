"""Oxstract API and web app.

Everything the frontend calls lives under `/api`. When a built frontend exists
(`FRONTEND_DIST`, or `frontend/dist` in a checkout), the same server also serves
it, so a private-network install needs only one port.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import NoReturn

import cv2
from fastapi import APIRouter, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import jobs, segments, sequence, store
from app.db import media_root
from app.detect import DetectorUnavailable, get_detector
from app.media import (
    MediaError,
    ToolMissing,
    extract_frame_png,
    frame_index,
    frame_time,
    probe,
    proxy_fps,
    read_frame,
    write_thumbnail,
)
from app.schemas import (
    AnalysisState,
    BBox,
    ClipOrder,
    ClipView,
    Cut,
    DetectionBox,
    DetectResponse,
    JobView,
    ProjectCreate,
    ProjectSummaryView,
    ProjectUpdate,
    ProjectView,
    ProxyState,
    ReferenceView,
    RenderSettings,
    RenderView,
    SegmentSettings,
    SegmentsView,
    SequenceSettings,
    SequenceView,
    Target,
    TargetIn,
    VideoView,
)

MIN_FREE_BYTES = 1024**3
_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,8}$")


def _not_found(what: str) -> NoReturn:
    raise HTTPException(status_code=404, detail=f"{what}이 없습니다.")


def _job_view(job: jobs.JobRecord) -> JobView:
    return JobView(
        id=job.id,
        kind=job.kind,
        ref_id=job.ref_id,
        status=job.status,  # type: ignore[arg-type]
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _video_view(video: store.VideoRecord) -> VideoView:
    proxy = None
    if video.proxy_job_id:
        job = jobs.get_job(video.proxy_job_id)
        if job is not None:
            proxy = ProxyState(
                status=job.status,  # type: ignore[arg-type]
                progress=job.progress,
                job_id=job.id,
                error=job.error,
            )
    return VideoView(
        id=video.id,
        filename=video.filename,
        content_type=video.content_type,
        duration=video.duration,
        width=video.width,
        height=video.height,
        fps=video.fps,
        rotation=video.rotation,
        video_codec=video.video_codec,
        has_audio=video.has_audio,
        variable_fps=video.variable_fps,
        proxy_fps=proxy_fps(video.fps),
        proxy=proxy,
        created_at=video.created_at,
    )


def _analysis_state(clip: store.ClipRecord) -> AnalysisState | None:
    job = jobs.get_job(clip.analysis_job_id) if clip.analysis_job_id else None
    if job is None:
        return None
    return AnalysisState(
        status=job.status,  # type: ignore[arg-type]
        progress=job.progress,
        stage=job.stage,
        job_id=job.id,
        error=job.error,
        ready=bool(clip.analysis_path and Path(clip.analysis_path).is_file()),
    )


def _clip_view(clip: store.ClipRecord) -> ClipView:
    return ClipView(
        id=clip.id,
        project_id=clip.project_id,
        position=clip.position,
        video=_video_view(clip.video),
        target=Target.model_validate(clip.target) if clip.target else None,
        analysis=_analysis_state(clip),
        cuts=[Cut.model_validate(cut) for cut in clip.cuts] if clip.cuts is not None else None,
    )


def _project_view(project: store.ProjectRecord) -> ProjectView:
    return ProjectView(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at,
        clips=[_clip_view(clip) for clip in project.clips],
        reference=ReferenceView.model_validate(project.reference) if project.reference else None,
    )


def _require_video(video_id: str) -> store.VideoRecord:
    video = store.get_video(video_id)
    if video is None or not Path(video.path).is_file():
        _not_found(f"영상 {video_id}")
    return video


def _require_proxy(video: store.VideoRecord) -> str:
    if not video.proxy_path or not Path(video.proxy_path).is_file():
        raise HTTPException(status_code=409, detail="미리보기가 아직 준비되지 않았습니다.")
    return video.proxy_path


def _clamp_box(bbox: BBox, width: int | None, height: int | None) -> BBox:
    """Keep the box inside the frame. Reject it if too little is left."""

    x1, y1 = max(0.0, bbox.x), max(0.0, bbox.y)
    x2, y2 = bbox.x + bbox.width, bbox.y + bbox.height
    if width:
        x2 = min(float(width), x2)
    if height:
        y2 = min(float(height), y2)
    if x2 - x1 < 4 or y2 - y1 < 4:
        raise HTTPException(status_code=422, detail="대상 영역이 너무 작거나 화면 밖에 있습니다.")
    return BBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)


api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Projects


@api.get("/projects", response_model=list[ProjectSummaryView])
def list_projects() -> list[ProjectSummaryView]:
    return [ProjectSummaryView(**vars(summary)) for summary in store.list_projects()]


@api.post("/projects", response_model=ProjectView, status_code=201)
def create_project(body: ProjectCreate) -> ProjectView:
    return _project_view(store.create_project(body.name.strip()))


@api.get("/projects/{project_id}", response_model=ProjectView)
def get_project(project_id: str) -> ProjectView:
    project = store.get_project(project_id)
    if project is None:
        _not_found(f"프로젝트 {project_id}")
    return _project_view(project)


@api.patch("/projects/{project_id}", response_model=ProjectView)
def rename_project(project_id: str, body: ProjectUpdate) -> ProjectView:
    try:
        return _project_view(store.rename_project(project_id, body.name.strip()))
    except store.NotFound:
        _not_found(f"프로젝트 {project_id}")


@api.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str) -> Response:
    try:
        store.delete_project(project_id)
    except store.NotFound:
        _not_found(f"프로젝트 {project_id}")
    return Response(status_code=204)


# Clips


@api.post("/projects/{project_id}/clips", response_model=ClipView, status_code=201)
async def upload_clip(project_id: str, file: UploadFile = File(...)) -> ClipView:
    """Upload a video and append it to the project. A proxy job is queued for it."""

    if store.get_project(project_id) is None:
        _not_found(f"프로젝트 {project_id}")
    content_type = file.content_type
    if (
        content_type
        and not content_type.startswith("video/")
        and content_type != "application/octet-stream"
    ):
        raise HTTPException(status_code=415, detail=f"{content_type}은 영상 형식이 아닙니다.")
    root = media_root()
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < MIN_FREE_BYTES:
        raise HTTPException(status_code=507, detail="서버 디스크 여유 공간이 1GB보다 적습니다.")

    video_id = uuid.uuid4().hex
    directory = store.video_dir(video_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename or "video").name or "video"
    suffix = Path(filename).suffix.lower()
    dest = directory / f"original{suffix if _SUFFIX.match(suffix) else ''}"
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        info = await run_in_threadpool(probe, dest)
    except MediaError:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=422, detail="영상 파일을 해석할 수 없습니다.") from None
    except ToolMissing as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    try:
        clip = store.add_clip(
            project_id,
            video_id=video_id,
            filename=filename,
            content_type=content_type,
            path=dest,
            info=info,
        )
    except store.NotFound:
        shutil.rmtree(directory, ignore_errors=True)
        _not_found(f"프로젝트 {project_id}")
    return _clip_view(clip)


@api.delete("/projects/{project_id}/clips/{clip_id}", status_code=204)
def remove_clip(project_id: str, clip_id: str) -> Response:
    try:
        store.remove_clip(project_id, clip_id)
    except store.NotFound:
        _not_found(f"클립 {clip_id}")
    return Response(status_code=204)


@api.put("/projects/{project_id}/clips/{clip_id}/target", response_model=ClipView)
def set_target(project_id: str, clip_id: str, body: TargetIn) -> ClipView:
    """Choose the object the clip follows. `t` snaps to the proxy frame it falls in."""

    clip = store.get_clip(project_id, clip_id)
    if clip is None:
        _not_found(f"클립 {clip_id}")
    video = clip.video
    if video.duration and body.t > video.duration:
        raise HTTPException(status_code=422, detail="영상 길이를 넘는 시각입니다.")
    fps = proxy_fps(video.fps)
    index = frame_index(body.t, fps)
    target = Target(
        t=frame_time(index, fps),
        frame_index=index,
        bbox=_clamp_box(body.bbox, video.width, video.height),
        source=body.source,
        class_name=body.class_name if body.source == "detect" else None,
        confidence=body.confidence if body.source == "detect" else None,
    )
    clip = store.set_target(project_id, clip_id, target.model_dump())
    _share_target(clip, target)
    return _clip_view(store.get_clip(project_id, clip_id) or clip)


def _share_target(clip: store.ClipRecord, target: Target) -> None:
    """Save what the target looks like and look for it in the project's other clips."""

    video = clip.video
    if not video.proxy_path or not Path(video.proxy_path).is_file():
        return
    try:
        frame = read_frame(video.proxy_path, target.t, fps=proxy_fps(video.fps))
    except MediaError:
        return
    sx = frame.shape[1] / (video.width or frame.shape[1])
    sy = frame.shape[0] / (video.height or frame.shape[0])
    box = target.bbox
    x1, y1 = max(0, round(box.x * sx)), max(0, round(box.y * sy))
    x2, y2 = round((box.x + box.width) * sx), round((box.y + box.height) * sy)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return
    path = store.reference_image(clip.project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), crop)
    store.share_target(clip.project_id, clip.id, target.class_name)


@api.post(
    "/projects/{project_id}/clips/{clip_id}/analysis", response_model=ClipView, status_code=202
)
def rerun_analysis(project_id: str, clip_id: str) -> ClipView:
    """Analyse the current target again (after a failure or a cancel)."""

    try:
        return _clip_view(store.queue_analysis(project_id, clip_id))
    except store.NotFound:
        _not_found(f"클립 {clip_id}")
    except store.MissingTarget as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@api.get("/projects/{project_id}/clips/{clip_id}/analysis")
def get_analysis(project_id: str, clip_id: str) -> FileResponse:
    """Per-sample boxes and motion signals (app/analysis.py) as JSON."""

    clip = store.get_clip(project_id, clip_id)
    if clip is None:
        _not_found(f"클립 {clip_id}")
    if not clip.analysis_path or not Path(clip.analysis_path).is_file():
        raise HTTPException(status_code=409, detail="분석이 아직 끝나지 않았습니다.")
    return FileResponse(clip.analysis_path, media_type="application/json")


def _analysed_clip(project_id: str, clip_id: str) -> tuple[store.ClipRecord, dict]:
    clip = store.get_clip(project_id, clip_id)
    if clip is None:
        _not_found(f"클립 {clip_id}")
    if not clip.analysis_path or not Path(clip.analysis_path).is_file():
        raise HTTPException(status_code=409, detail="분석이 아직 끝나지 않았습니다.")
    return clip, json.loads(Path(clip.analysis_path).read_text(encoding="utf-8"))


def _segments_view(clip: store.ClipRecord, settings: SegmentSettings) -> SegmentsView:
    cuts = [Cut.model_validate(cut) for cut in clip.cuts or []]
    return SegmentsView(
        params=settings.params,
        edits=settings.edits,
        cuts=cuts,
        duration=clip.video.duration or 0.0,
        kept=round(sum(cut.end - cut.start for cut in cuts), 3),
    )


@api.get("/projects/{project_id}/clips/{clip_id}/segments", response_model=SegmentsView)
def get_segments(project_id: str, clip_id: str) -> SegmentsView:
    """How the clip is cut now: settings, manual edits, and the parts they give."""

    clip, _ = _analysed_clip(project_id, clip_id)
    settings = SegmentSettings.model_validate(
        {"params": clip.segment_params or {}, "edits": clip.segment_edits or []}
    )
    return _segments_view(clip, settings)


@api.put("/projects/{project_id}/clips/{clip_id}/segments", response_model=SegmentsView)
def put_segments(project_id: str, clip_id: str, body: SegmentSettings) -> SegmentsView:
    """Recut with new settings or edits. Takes milliseconds, so the editor calls it live."""

    clip, analysis = _analysed_clip(project_id, clip_id)
    params = body.params.model_dump()
    edits = [edit.model_dump() for edit in body.edits]
    cuts = segments.compute(analysis, clip.video.duration, *segments.settings(params, edits))
    updated = store.set_segments(project_id, clip_id, params, edits, segments.as_json(cuts))
    return _segments_view(updated, body)


@api.delete("/projects/{project_id}/clips/{clip_id}/target", response_model=ClipView)
def clear_target(project_id: str, clip_id: str) -> ClipView:
    try:
        clip = store.set_target(project_id, clip_id, None)
    except store.NotFound:
        _not_found(f"클립 {clip_id}")
    store.forget_shared_target(project_id, clip_id)
    return _clip_view(clip)


@api.put("/projects/{project_id}/clips/order", response_model=ProjectView)
def reorder_clips(project_id: str, body: ClipOrder) -> ProjectView:
    try:
        return _project_view(store.reorder_clips(project_id, body.clip_ids))
    except store.NotFound:
        _not_found(f"프로젝트 {project_id}")
    except store.InvalidOrder as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


# Videos


@api.get("/videos/{video_id}", response_model=VideoView)
def get_video(video_id: str) -> VideoView:
    return _video_view(_require_video(video_id))


@api.get("/videos/{video_id}/file")
def get_video_file(video_id: str) -> FileResponse:
    video = _require_video(video_id)
    return FileResponse(
        video.path, media_type=video.content_type or "video/mp4", filename=video.filename
    )


@api.get("/videos/{video_id}/proxy")
def get_proxy(video_id: str) -> FileResponse:
    return FileResponse(_require_proxy(_require_video(video_id)), media_type="video/mp4")


@api.post("/videos/{video_id}/proxy", response_model=JobView, status_code=202)
def retry_proxy(video_id: str) -> JobView:
    _require_video(video_id)
    job = jobs.get_job(store.queue_proxy(video_id))
    assert job is not None
    return _job_view(job)


@api.get("/videos/{video_id}/frame")
def get_frame(video_id: str, t: float = Query(ge=0)) -> Response:
    """The frame at `t`. From the proxy (exact frame index) when it exists."""

    video = _require_video(video_id)
    has_proxy = video.playable_path != video.path
    try:
        png = extract_frame_png(
            video.playable_path, t, fps=proxy_fps(video.fps) if has_proxy else None
        )
    except MediaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return Response(content=png, media_type="image/png")


@api.get("/videos/{video_id}/thumb")
def get_thumbnail(video_id: str) -> FileResponse:
    video = _require_video(video_id)
    thumb = Path(video.path).parent / "thumb.jpg"
    if not thumb.is_file():
        t = min(1.0, (video.duration or 0) * 0.1)
        try:
            write_thumbnail(video.playable_path, t, thumb)
        except MediaError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
    return FileResponse(thumb, media_type="image/jpeg")


@api.post("/videos/{video_id}/detect", response_model=DetectResponse)
async def detect_frame(video_id: str, t: float = Query(ge=0)) -> DetectResponse:
    """Run the object detector on the proxy frame at `t`. Boxes come back in source pixels."""

    video = _require_video(video_id)
    proxy = _require_proxy(video)
    fps = proxy_fps(video.fps)
    index = frame_index(t, fps)
    try:
        detector = await run_in_threadpool(get_detector)
    except DetectorUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    try:
        frame = await run_in_threadpool(read_frame, proxy, frame_time(index, fps), fps=fps)
    except MediaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    detections = await run_in_threadpool(detector, frame)
    frame_height, frame_width = frame.shape[:2]
    scale_x = (video.width or frame_width) / frame_width
    scale_y = (video.height or frame_height) / frame_height
    return DetectResponse(
        t=frame_time(index, fps),
        frame_index=index,
        boxes=[
            DetectionBox(
                bbox=BBox(
                    x=d.x * scale_x,
                    y=d.y * scale_y,
                    width=d.width * scale_x,
                    height=d.height * scale_y,
                ),
                class_name=d.class_name,
                confidence=d.confidence,
            )
            for d in detections
        ],
    )


# Sequence and renders


def _sequence_view(project: store.ProjectRecord) -> SequenceView:
    settings = sequence.settings_of(project)
    items = sequence.items(project, settings)
    return SequenceView(
        **settings.model_dump(),
        items=items,
        total=sequence.total_seconds(items, settings),
    )


@api.get("/projects/{project_id}/sequence", response_model=SequenceView)
def get_sequence(project_id: str) -> SequenceView:
    """The result's running order with the transition after every cut."""

    project = store.get_project(project_id)
    if project is None:
        _not_found(f"프로젝트 {project_id}")
    return _sequence_view(project)


@api.put("/projects/{project_id}/sequence", response_model=SequenceView)
def put_sequence(project_id: str, body: SequenceSettings) -> SequenceView:
    try:
        project = store.set_sequence(project_id, body.model_dump(exclude_none=False))
    except store.NotFound:
        _not_found(f"프로젝트 {project_id}")
    return _sequence_view(project)


_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def _render_view(record: store.RenderRecord) -> RenderView:
    job = jobs.get_job(record.job_id)
    return RenderView(
        id=record.id,
        project_id=record.project_id,
        settings=RenderSettings.model_validate(record.settings),
        created_at=record.created_at,
        status=job.status if job else "failed",  # type: ignore[arg-type]
        progress=job.progress if job else 0.0,
        stage=job.stage if job else None,
        error=job.error if job else "작업 기록이 없습니다.",
        ready=bool(record.path and Path(record.path).is_file()),
        filename=record.filename,
        duration=record.duration,
        size_bytes=record.size_bytes,
    )


@api.post("/projects/{project_id}/renders", response_model=RenderView, status_code=202)
def create_render(project_id: str, body: RenderSettings) -> RenderView:
    """Queue a render of the whole project with the current cuts and transitions."""

    project = store.get_project(project_id)
    if project is None:
        _not_found(f"프로젝트 {project_id}")
    if not any(clip.cuts for clip in project.clips):
        raise HTTPException(status_code=409, detail="남길 구간이 있는 클립이 없습니다.")
    name = _UNSAFE.sub("_", project.name).strip(" ._") or "oxstract"
    record = store.create_render(project_id, body.model_dump(), f"{name}.mp4")
    return _render_view(record)


@api.get("/projects/{project_id}/renders", response_model=list[RenderView])
def list_renders(project_id: str) -> list[RenderView]:
    return [_render_view(record) for record in store.list_renders(project_id)]


@api.get("/renders/{render_id}/file")
def get_render_file(render_id: str, download: bool = False) -> FileResponse:
    record = store.get_render(render_id)
    if record is None or not record.path or not Path(record.path).is_file():
        _not_found(f"결과 {render_id}")
    return FileResponse(
        record.path,
        media_type="video/mp4",
        filename=record.filename,
        content_disposition_type="attachment" if download else "inline",
    )


@api.delete("/renders/{render_id}", status_code=204)
def delete_render(render_id: str) -> Response:
    try:
        store.delete_render(render_id)
    except store.NotFound:
        _not_found(f"결과 {render_id}")
    return Response(status_code=204)


# Jobs


@api.get("/jobs", response_model=list[JobView])
def list_jobs(active: bool = False) -> list[JobView]:
    return [_job_view(job) for job in jobs.list_jobs(active_only=active)]


@api.get("/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str) -> JobView:
    job = jobs.get_job(job_id)
    if job is None:
        _not_found(f"작업 {job_id}")
    return _job_view(job)


@api.post("/jobs/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str) -> JobView:
    job = jobs.request_cancel(job_id)
    if job is None:
        _not_found(f"작업 {job_id}")
    return _job_view(job)


@api.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    """Server-sent events with the job state, until it finishes."""

    if jobs.get_job(job_id) is None:
        _not_found(f"작업 {job_id}")

    async def stream():
        last = None
        while not await request.is_disconnected():
            job = await run_in_threadpool(jobs.get_job, job_id)
            if job is None:
                return
            payload = _job_view(job).model_dump_json()
            if payload != last:
                last = payload
                yield f"event: job\ndata: {payload}\n\n"
            if job.status in jobs.TERMINAL:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _frontend_dist() -> Path | None:
    configured = os.environ.get("FRONTEND_DIST")
    dist = Path(configured) if configured else Path(__file__).resolve().parents[2] / "frontend/dist"
    return dist if (dist / "index.html").is_file() else None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Oxstract",
        version="0.2.0",
        description="지정한 객체가 움직이는 구간만 이어 붙이는 셀프호스팅 영상 편집기.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(api)

    dist = _frontend_dist()
    if dist is not None:
        root = dist.resolve()
        if (root / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path == "api" or path.startswith("api/"):
                _not_found(f"경로 /{path}")
            candidate = (root / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate)
            return FileResponse(root / "index.html")

    return app


app = create_app()
