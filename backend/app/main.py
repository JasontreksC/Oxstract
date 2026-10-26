"""Oxstract API stub.

Routes follow the plan sections 4, 5.0, and 5.5. Handlers validate the
contract and then report that the pipeline is not implemented yet.
"""

from __future__ import annotations

import os
from typing import NoReturn

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    DetectResponse,
    JobCreate,
    JobView,
    RenderAccepted,
    SegmentList,
    VideoCreated,
)

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


@app.post("/videos", response_model=VideoCreated)
async def upload_video(file: UploadFile = File(...)) -> VideoCreated:
    name = file.filename or "video"
    _not_implemented(f"업로드({name})는 아직 구현되지 않았습니다.")


@app.get("/videos/{video_id}/frame")
def get_frame(video_id: str, t: float = Query(ge=0)) -> None:
    _not_implemented(f"영상 {video_id}의 t={t} 프레임은 아직 구현되지 않았습니다.")


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
