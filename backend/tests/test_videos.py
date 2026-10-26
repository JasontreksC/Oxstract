"""M1: upload storage, metadata probing, frame extraction, file serving."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_video(path: Path, seconds: int = 2, fps: int = 10) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    frame = np.zeros((48, 64, 3), np.uint8)
    for i in range(seconds * fps):
        frame[:] = ((i * 10) % 256, 0, 0)
        writer.write(frame)
    writer.release()


@pytest.fixture()
def clip_path(tmp_path: Path) -> Path:
    path = tmp_path / "clip.mp4"
    _make_video(path)
    return path


def _upload(clip_path: Path):
    with clip_path.open("rb") as handle:
        return client.post("/videos", files={"file": ("clip.mp4", handle, "video/mp4")})


def test_upload_stores_and_probes(clip_path: Path) -> None:
    response = _upload(clip_path)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "clip.mp4"
    assert body["content_type"] == "video/mp4"
    assert body["duration"] == pytest.approx(2.0, abs=0.3)
    assert body["width"] == 64
    assert body["height"] == 48


def test_frame_returns_png_with_video_dimensions(clip_path: Path) -> None:
    video_id = _upload(clip_path).json()["id"]

    response = client.get(f"/videos/{video_id}/frame", params={"t": 0.5})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape == (48, 64, 3)


def test_frame_unknown_video_is_404() -> None:
    response = client.get("/videos/missing/frame", params={"t": 0})

    assert response.status_code == 404


def test_frame_past_end_is_404(clip_path: Path) -> None:
    video_id = _upload(clip_path).json()["id"]

    response = client.get(f"/videos/{video_id}/frame", params={"t": 9999})

    assert response.status_code == 404


def test_file_serves_bytes(clip_path: Path) -> None:
    video_id = _upload(clip_path).json()["id"]

    response = client.get(f"/videos/{video_id}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert len(response.content) > 1000


def test_file_unknown_video_is_404() -> None:
    assert client.get("/videos/missing/file").status_code == 404


def test_upload_rejects_unreadable_video() -> None:
    response = client.post(
        "/videos",
        files={"file": ("clip.mp4", b"not-a-video", "video/mp4")},
    )

    assert response.status_code == 422


def test_upload_rejects_non_video_content_type() -> None:
    response = client.post(
        "/videos",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
