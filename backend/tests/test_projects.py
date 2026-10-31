"""Projects, clip upload and order, proxies made by the worker. Needs FFmpeg."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from conftest import make_video, requires_ffmpeg
from fastapi.testclient import TestClient

from app import worker
from app.detect import model_path
from app.main import app
from app.media import ffprobe_bin

pytestmark = requires_ffmpeg
client = TestClient(app)


def detect_model_present() -> bool:
    return model_path().is_file()


def _project(name: str = "주말 산책") -> dict:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _upload(project_id: str, path: Path, content_type: str = "video/mp4"):
    with path.open("rb") as handle:
        return client.post(
            f"/api/projects/{project_id}/clips", files={"file": (path.name, handle, content_type)}
        )


@pytest.fixture()
def clip_path(tmp_path: Path) -> Path:
    return make_video(tmp_path / "walk.mp4")


def test_project_crud() -> None:
    project = _project()
    assert project["clips"] == []

    renamed = client.patch(f"/api/projects/{project['id']}", json={"name": "산책 2"})
    assert renamed.json()["name"] == "산책 2"

    listed = client.get("/api/projects").json()
    assert [(p["id"], p["clip_count"]) for p in listed] == [(project["id"], 0)]

    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404


def test_project_name_is_required() -> None:
    assert client.post("/api/projects", json={"name": ""}).status_code == 422


def test_upload_probes_and_queues_proxy(clip_path: Path) -> None:
    project = _project()

    response = _upload(project["id"], clip_path)

    assert response.status_code == 201
    video = response.json()["video"]
    assert video["filename"] == "walk.mp4"
    assert video["duration"] == pytest.approx(2.0, abs=0.1)
    assert (video["width"], video["height"]) == (320, 240)
    assert video["fps"] == pytest.approx(10)
    assert video["proxy_fps"] == 10
    assert video["video_codec"] == "h264"
    assert video["has_audio"] is True
    assert video["proxy"]["status"] == "queued"
    assert client.get(f"/api/videos/{video['id']}/proxy").status_code == 409


def test_worker_makes_playable_proxy(clip_path: Path) -> None:
    project = _project()
    video_id = _upload(project["id"], clip_path).json()["video"]["id"]

    assert worker.run_once() is True
    assert worker.run_once() is False

    video = client.get(f"/api/videos/{video_id}").json()
    assert video["proxy"]["status"] == "done"
    assert video["proxy"]["progress"] == 1
    response = client.get(f"/api/videos/{video_id}/proxy")
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"


def test_rotated_phone_video_is_upright(tmp_path: Path) -> None:
    path = make_video(tmp_path / "phone.mp4", size="640x360", audio=False, rotation=90)
    project = _project()

    video = _upload(project["id"], path).json()["video"]
    assert video["rotation"] in (90, 270)
    assert (video["width"], video["height"]) == (360, 640)
    assert video["has_audio"] is False

    worker.run_once()
    assert client.get(f"/api/videos/{video['id']}/proxy").status_code == 200
    stored = tmp_path / "media" / "videos" / video["id"] / "proxy.mp4"
    streams = json.loads(
        subprocess.run(
            [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_streams", str(stored)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )["streams"]
    picture = next(s for s in streams if s["codec_type"] == "video")
    assert (picture["width"], picture["height"]) == (360, 640)


def test_large_video_proxy_short_side_is_720(tmp_path: Path) -> None:
    path = make_video(tmp_path / "big.mp4", size="1920x1080", seconds=1, audio=False)
    project = _project()
    video_id = _upload(project["id"], path).json()["video"]["id"]

    worker.run_once()

    frame = client.get(f"/api/videos/{video_id}/frame", params={"t": 0.5})
    image = cv2.imdecode(np.frombuffer(frame.content, np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[:2] == (720, 1280)


def test_frame_and_thumbnail(clip_path: Path) -> None:
    project = _project()
    video_id = _upload(project["id"], clip_path).json()["video"]["id"]

    frame = client.get(f"/api/videos/{video_id}/frame", params={"t": 0.5})
    assert frame.status_code == 200
    assert frame.headers["content-type"] == "image/png"
    assert client.get(f"/api/videos/{video_id}/frame", params={"t": 9999}).status_code == 404

    thumb = client.get(f"/api/videos/{video_id}/thumb")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"


def test_original_file_supports_range(clip_path: Path) -> None:
    project = _project()
    video_id = _upload(project["id"], clip_path).json()["video"]["id"]

    response = client.get(f"/api/videos/{video_id}/file", headers={"Range": "bytes=0-99"})

    assert response.status_code == 206
    assert len(response.content) == 100


def test_reorder_and_remove_clips(clip_path: Path, tmp_path: Path) -> None:
    project = _project()
    first = _upload(project["id"], clip_path).json()
    second = _upload(project["id"], make_video(tmp_path / "b.mp4", seconds=1)).json()

    reordered = client.put(
        f"/api/projects/{project['id']}/clips/order",
        json={"clip_ids": [second["id"], first["id"]]},
    )
    assert [c["id"] for c in reordered.json()["clips"]] == [second["id"], first["id"]]

    bad = client.put(f"/api/projects/{project['id']}/clips/order", json={"clip_ids": [first["id"]]})
    assert bad.status_code == 422

    removed = client.delete(f"/api/projects/{project['id']}/clips/{second['id']}")
    assert removed.status_code == 204
    clips = client.get(f"/api/projects/{project['id']}").json()["clips"]
    assert [(c["id"], c["position"]) for c in clips] == [(first["id"], 0)]
    assert client.get(f"/api/videos/{second['video']['id']}").status_code == 404
    assert not (tmp_path / "media" / "videos" / second["video"]["id"]).exists()


def test_delete_project_removes_its_videos(clip_path: Path, tmp_path: Path) -> None:
    project = _project()
    video_id = _upload(project["id"], clip_path).json()["video"]["id"]

    client.delete(f"/api/projects/{project['id']}")

    assert client.get(f"/api/videos/{video_id}").status_code == 404
    assert not (tmp_path / "media" / "videos" / video_id).exists()
    assert worker.run_once() is False  # its queued proxy job was canceled


def test_upload_to_unknown_project_is_404(clip_path: Path) -> None:
    assert _upload("missing", clip_path).status_code == 404


def test_upload_rejects_unreadable_video() -> None:
    project = _project()
    response = client.post(
        f"/api/projects/{project['id']}/clips",
        files={"file": ("clip.mp4", b"not-a-video", "video/mp4")},
    )
    assert response.status_code == 422
    assert client.get(f"/api/projects/{project['id']}").json()["clips"] == []


def test_upload_rejects_non_video_content_type() -> None:
    project = _project()
    response = client.post(
        f"/api/projects/{project['id']}/clips",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_failed_proxy_can_be_retried(clip_path: Path) -> None:
    project = _project()
    video = _upload(project["id"], clip_path).json()["video"]

    retry = client.post(f"/api/videos/{video['id']}/proxy")

    assert retry.status_code == 202
    assert retry.json()["id"] != video["proxy"]["job_id"]
    assert client.get(f"/api/videos/{video['id']}").json()["proxy"]["job_id"] == retry.json()["id"]


def _gray_steps_video(path: Path, frames: int = 30, fps: int = 10) -> Path:
    """Each frame a flat grey 8 levels brighter than the last, so a frame tells its index."""

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 120))
    for index in range(frames):
        writer.write(np.full((120, 160, 3), 8 * index, np.uint8))
    writer.release()
    return path


def test_frame_reads_exact_proxy_frame(tmp_path: Path) -> None:
    project = _project()
    video_id = _upload(project["id"], _gray_steps_video(tmp_path / "steps.mp4")).json()["video"][
        "id"
    ]
    worker.run_once()

    for index in (0, 1, 7, 15, 29):
        for t in (index / 10, (index + 0.5) / 10, (index + 0.99) / 10):
            png = client.get(f"/api/videos/{video_id}/frame", params={"t": t}).content
            image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
            assert abs(float(image.mean()) - 8 * index) < 4, (index, t)


def _ready_clip(tmp_path: Path, **video) -> tuple[dict, dict]:
    project = _project()
    clip = _upload(project["id"], make_video(tmp_path / "walk.mp4", **video)).json()
    worker.run_once()
    return project, clip


def test_set_and_clear_target(tmp_path: Path) -> None:
    project, clip = _ready_clip(tmp_path)
    url = f"/api/projects/{project['id']}/clips/{clip['id']}/target"

    saved = client.put(
        url,
        json={
            "t": 1.23,
            "bbox": {"x": -10, "y": 20, "width": 100, "height": 500},
            "source": "drag",
            "class_name": "dog",
        },
    )

    assert saved.status_code == 200
    target = saved.json()["target"]
    assert target["frame_index"] == 12
    assert target["t"] == pytest.approx(1.25)
    assert target["bbox"] == {"x": 0, "y": 20, "width": 90, "height": 220}
    assert target["source"] == "drag"
    assert target["class_name"] is None  # only detector picks carry a class
    stored = client.get(f"/api/projects/{project['id']}").json()["clips"][0]["target"]
    assert stored == target

    cleared = client.delete(url)
    assert cleared.status_code == 200
    assert cleared.json()["target"] is None


def test_target_from_detection_keeps_class(tmp_path: Path) -> None:
    project, clip = _ready_clip(tmp_path)

    saved = client.put(
        f"/api/projects/{project['id']}/clips/{clip['id']}/target",
        json={
            "t": 0.5,
            "bbox": {"x": 10, "y": 10, "width": 50, "height": 40},
            "source": "detect",
            "class_name": "dog",
            "confidence": 0.91,
        },
    )

    assert saved.json()["target"]["class_name"] == "dog"
    assert saved.json()["target"]["confidence"] == pytest.approx(0.91)


def test_target_rejects_bad_input(tmp_path: Path) -> None:
    project, clip = _ready_clip(tmp_path)
    url = f"/api/projects/{project['id']}/clips/{clip['id']}/target"
    box = {"x": 10, "y": 10, "width": 50, "height": 40}

    outside = {"x": 400, "y": 10, "width": 50, "height": 40}
    assert client.put(url, json={"t": 0.5, "bbox": outside, "source": "drag"}).status_code == 422
    assert client.put(url, json={"t": 99, "bbox": box, "source": "drag"}).status_code == 422
    assert client.put(url, json={"t": 0.5, "bbox": box, "source": "lasso"}).status_code == 422
    missing = f"/api/projects/{project['id']}/clips/nope/target"
    assert client.put(missing, json={"t": 0.5, "bbox": box, "source": "drag"}).status_code == 404


def test_detect_needs_proxy(clip_path: Path) -> None:
    project = _project()
    video_id = _upload(project["id"], clip_path).json()["video"]["id"]

    assert client.post(f"/api/videos/{video_id}/detect", params={"t": 0.5}).status_code == 409


def test_detect_without_model_is_503(tmp_path: Path, monkeypatch) -> None:
    from app import detect

    monkeypatch.setenv("DETECT_MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setattr(detect, "_detector", None)
    _, clip = _ready_clip(tmp_path)

    response = client.post(f"/api/videos/{clip['video']['id']}/detect", params={"t": 0.5})

    assert response.status_code == 503
    assert "모델" in response.json()["detail"]


@pytest.mark.skipif(not detect_model_present(), reason="models/yolo11n.onnx가 없습니다")
def test_detect_with_model_returns_source_pixel_boxes(tmp_path: Path) -> None:
    _, clip = _ready_clip(tmp_path, size="1920x1080", seconds=1, audio=False)

    response = client.post(f"/api/videos/{clip['video']['id']}/detect", params={"t": 0.31})

    assert response.status_code == 200
    body = response.json()
    assert body["frame_index"] == 3
    assert body["t"] == pytest.approx(0.35)
    for box in body["boxes"]:
        assert 0 <= box["bbox"]["x"] and box["bbox"]["x"] + box["bbox"]["width"] <= 1920.01
        assert 0 <= box["bbox"]["y"] and box["bbox"]["y"] + box["bbox"]["height"] <= 1080.01


def _moving_clip(tmp_path: Path) -> tuple[dict, dict]:
    from synthetic import make_clip

    project = _project()
    clip = _upload(project["id"], make_clip(tmp_path / "slide.mp4", "move")).json()
    worker.run_once()  # proxy
    return project, clip


def test_saving_a_target_analyses_the_clip(tmp_path: Path) -> None:
    from synthetic import BOX, START

    project, clip = _moving_clip(tmp_path)
    base = f"/api/projects/{project['id']}/clips/{clip['id']}"
    x, y, w, h = BOX
    saved = client.put(
        f"{base}/target",
        json={"t": 0.5, "bbox": {"x": x, "y": y, "width": w, "height": h}, "source": "drag"},
    ).json()
    assert saved["analysis"]["status"] == "queued"
    assert client.get(f"{base}/analysis").status_code == 409

    assert worker.run_once() is True

    state = client.get(f"/api/projects/{project['id']}").json()["clips"][0]["analysis"]
    assert state["status"] == "done"
    assert state["ready"] is True
    result = client.get(f"{base}/analysis").json()
    samples = result["samples"]
    assert len(samples["t"]) == 30
    assert all(samples["visible"])
    assert samples["x"][-1] == pytest.approx(START[0] + 150, abs=12)
    assert max(samples["move"]) > 0.5


def test_new_target_replaces_the_queued_analysis(tmp_path: Path) -> None:
    project, clip = _moving_clip(tmp_path)
    base = f"/api/projects/{project['id']}/clips/{clip['id']}"
    box = {"x": 265, "y": 125, "width": 110, "height": 110}

    first = client.put(f"{base}/target", json={"t": 0.5, "bbox": box, "source": "drag"}).json()
    second = client.put(f"{base}/target", json={"t": 0.2, "bbox": box, "source": "drag"}).json()

    assert first["analysis"]["job_id"] != second["analysis"]["job_id"]
    assert client.get(f"/api/jobs/{first['analysis']['job_id']}").json()["status"] == "canceled"
    cleared = client.delete(f"{base}/target").json()
    assert cleared["analysis"] is None
    assert client.get(f"/api/jobs/{second['analysis']['job_id']}").json()["status"] == "canceled"
    assert client.post(f"{base}/analysis").status_code == 409  # no target to analyse


def _analysed_moving_clip(tmp_path: Path) -> tuple[str, dict]:
    from synthetic import BOX

    project, clip = _moving_clip(tmp_path)
    base = f"/api/projects/{project['id']}/clips/{clip['id']}"
    x, y, w, h = BOX
    client.put(
        f"{base}/target",
        json={"t": 0.5, "bbox": {"x": x, "y": y, "width": w, "height": h}, "source": "drag"},
    )
    worker.run_once()  # analysis
    return base, project


def test_analysis_cuts_the_clip_right_away(tmp_path: Path) -> None:
    base, project = _analysed_moving_clip(tmp_path)

    cuts = client.get(f"/api/projects/{project['id']}").json()["clips"][0]["cuts"]

    # The disk slides from 1 s to 2 s; default padding is 0.3 s.
    assert len(cuts) == 1
    assert cuts[0]["start"] == pytest.approx(0.7, abs=0.25)
    assert cuts[0]["end"] == pytest.approx(2.3, abs=0.25)

    view = client.get(f"{base}/segments").json()
    assert view["params"]["sensitivity"] == 1.0
    assert view["edits"] == []
    assert view["kept"] == pytest.approx(cuts[0]["end"] - cuts[0]["start"], abs=0.01)


def test_recut_with_settings_and_edits_is_kept(tmp_path: Path) -> None:
    from synthetic import BOX

    base, project = _analysed_moving_clip(tmp_path)

    view = client.put(
        f"{base}/segments",
        json={"params": {"padding": 0}, "edits": [{"op": "keep", "start": 2.5, "end": 2.9}]},
    ).json()

    assert [c["edited"] for c in view["cuts"]] == [False, True]
    assert view["cuts"][1]["start"] == pytest.approx(2.5)
    assert client.get(f"/api/projects/{project['id']}").json()["clips"][0]["cuts"] == view["cuts"]

    # A new target re-analyses and recuts, keeping the settings and edits.
    x, y, w, h = BOX
    client.put(
        f"{base}/target",
        json={"t": 0.4, "bbox": {"x": x, "y": y, "width": w, "height": h}, "source": "drag"},
    )
    assert client.get(f"/api/projects/{project['id']}").json()["clips"][0]["cuts"] is None
    worker.run_once()
    again = client.get(f"{base}/segments").json()
    assert again["params"]["padding"] == 0
    assert again["cuts"][-1]["start"] == pytest.approx(2.5)


def test_segments_need_analysis_and_valid_edits(tmp_path: Path) -> None:
    project, clip = _moving_clip(tmp_path)
    base = f"/api/projects/{project['id']}/clips/{clip['id']}"
    assert client.get(f"{base}/segments").status_code == 409

    base, _ = _analysed_moving_clip(tmp_path)
    bad = {"edits": [{"op": "keep", "start": 3, "end": 2}]}
    assert client.put(f"{base}/segments", json=bad).status_code == 422
    assert client.put(f"{base}/segments", json={"params": {"sensitivity": 9}}).status_code == 422
