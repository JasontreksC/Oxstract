"""Oxstract API.

Routes follow the plan sections 4, 5.0, and 5.5. Upload, frame, and file
serving work (M1). Detection, jobs, and rendering still report 501.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import NoReturn

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app.media import MediaError, extract_frame_png, probe
from app.schemas import (
    DetectResponse,
    JobCreate,
    JobView,
    RenderAccepted,
    SegmentList,
    VideoCreated,
)
from app.store import VideoRecord, get_video, media_root, save_video

app = FastAPI(
    title="Oxstract",
    version="0.1.0",
    description="객체 움직임 구간을 잘라 이어 붙이는 로컬 영상 편집 API (스텁).",
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    if not raw.strip():
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    return [item.strip() for item in raw.split(",") if item.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _not_implemented(detail: str) -> NoReturn:
    raise HTTPException(status_code=501, detail=detail)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/videos", response_model=VideoCreated, status_code=201)
async def upload_video(file: UploadFile = File(...)) -> VideoCreated:
    content_type = file.content_type
    if (
        content_type
        and not content_type.startswith("video/")
        and content_type != "application/octet-stream"
    ):
        raise HTTPException(status_code=415, detail=f"{content_type}은 영상 형식이 아닙니다.")
    video_id = uuid.uuid4().hex
    directory = media_root() / "videos" / video_id
    directory.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "video").name
    if name in ("", ".", ".."):
        name = "video"
    dest = directory / name
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    try:
        duration, width, height = probe(str(dest))
    except MediaError:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=422, detail="영상 파일을 해석할 수 없습니다.") from None
    record = save_video(
        VideoRecord(
            id=video_id,
            filename=name,
            content_type=content_type,
            duration=duration,
            width=width,
            height=height,
            path=str(dest),
        )
    )
    return VideoCreated(
        id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        duration=record.duration,
        width=record.width,
        height=record.height,
    )


@app.get("/videos/{video_id}/frame")
def get_frame(video_id: str, t: float = Query(ge=0)) -> Response:
    record = get_video(video_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"영상 {video_id}이 없습니다.")
    try:
        png = extract_frame_png(record.path, t)
    except MediaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return Response(content=png, media_type="image/png")


@app.get("/videos/{video_id}/file")
def get_video_file(video_id: str) -> FileResponse:
    record = get_video(video_id)
    if record is None or not Path(record.path).is_file():
        raise HTTPException(status_code=404, detail=f"영상 {video_id}이 없습니다.")
    return FileResponse(
        record.path,
        media_type=record.content_type or "video/mp4",
        filename=record.filename,
    )


@app.post("/videos/{video_id}/detect", response_model=DetectResponse)
def detect_frame(video_id: str, t: float = Query(ge=0)) -> DetectResponse:
    _not_implemented(f"영상 {video_id}의 t={t} 탐지는 아직 구현되지 않았습니다.")


@app.post("/jobs", response_model=JobView, status_code=202)
def create_job(body: JobCreate) -> JobView:
    _not_implemented(f"영상 {body.video_id}의 작업 생성은 아직 구현되지 않았습니다.")


@app.get("/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str) -> JobView:
    _not_implemented(f"작업 {job_id} 조회는 아직 구현되지 않았습니다.")


@app.patch("/jobs/{job_id}/segments", response_model=SegmentList)
def update_segments(job_id: str, body: SegmentList) -> SegmentList:
    count = len(body.segments)
    _not_implemented(f"작업 {job_id}의 구간 {count}개 수정은 아직 구현되지 않았습니다.")


@app.post("/jobs/{job_id}/render", response_model=RenderAccepted, status_code=202)
def render_job(job_id: str) -> RenderAccepted:
    _not_implemented(f"작업 {job_id} 렌더는 아직 구현되지 않았습니다.")


@app.get("/jobs/{job_id}/output")
def get_output(job_id: str) -> None:
    raise HTTPException(status_code=404, detail=f"작업 {job_id}의 결과 영상이 없습니다.")


@app.websocket("/jobs/{job_id}/progress")
async def job_progress(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "job_id": job_id,
            "stage": "error",
            "progress": 0,
            "message": "아직 구현되지 않았습니다.",
        }
    )
    await websocket.close()
