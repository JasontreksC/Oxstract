"""Sequence of cuts with transitions, and rendering it to one file. Needs FFmpeg."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from conftest import requires_ffmpeg
from fastapi.testclient import TestClient
from test_projects import _analysed_moving_clip

from app import worker
from app.main import app
from app.media import ffprobe_bin
from app.render import find_font, output_size

client = TestClient(app)
CARD = {
    "type": "text_card",
    "duration": 1.0,
    "bg_color": "#202020",
    "text": "다음 장면",
    "font_size": 48,
    "font_color": "#FFFFFF",
}


def test_output_size_follows_the_first_clip() -> None:
    assert output_size("1080", 1920, 1080) == (1920, 1080)
    assert output_size("720", 1080, 1920) == (720, 1280)
    assert output_size("source", 3840, 2160) == (3840, 2160)
    assert output_size("source", 7680, 4320) == (3840, 2160)


@requires_ffmpeg
def test_sequence_lists_cuts_with_transitions(tmp_path: Path) -> None:
    base, project = _analysed_moving_clip(tmp_path)
    client.put(f"{base}/segments", json={"edits": [{"op": "keep", "start": 2.6, "end": 2.95}]})
    url = f"/api/projects/{project['id']}/sequence"

    first = client.get(url).json()
    assert len(first["items"]) == 2
    assert first["items"][0]["transition_after"]["type"] == "none"
    assert first["items"][-1]["transition_after"] is None

    key = first["items"][0]["key"]
    saved = client.put(
        url,
        json={
            "default": {"type": "fade", "duration": 0.3},
            "overrides": {key: CARD},
            "intro": CARD,
        },
    ).json()
    assert saved["items"][0]["transition_after"]["type"] == "text_card"
    cuts = sum(item["end"] - item["start"] for item in saved["items"])
    assert saved["total"] == pytest.approx(cuts + 2.0, abs=0.01)  # two 1 s cards

    bad = client.put(url, json={"intro": {"type": "fade", "duration": 1}})
    assert bad.status_code == 422


@requires_ffmpeg
def test_render_makes_one_playable_file(tmp_path: Path, monkeypatch) -> None:
    base, project = _analysed_moving_clip(tmp_path)
    client.put(f"{base}/segments", json={"edits": [{"op": "keep", "start": 2.6, "end": 2.95}]})
    items = client.get(f"/api/projects/{project['id']}/sequence").json()["items"]
    with_card = find_font() is not None
    sequence = {"default": {"type": "fade", "duration": 0.2}}
    if with_card:
        sequence["outro"] = CARD
    client.put(f"/api/projects/{project['id']}/sequence", json=sequence)

    queued = client.post(
        f"/api/projects/{project['id']}/renders", json={"resolution": "720", "quality": "small"}
    )
    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    assert worker.run_once() is True

    [done] = client.get(f"/api/projects/{project['id']}/renders").json()
    assert done["status"] == "done", done["error"]
    assert done["ready"] is True
    assert done["filename"] == "주말 산책.mp4"
    expected = sum(item["end"] - item["start"] for item in items) + (1.0 if with_card else 0)
    assert done["duration"] == pytest.approx(expected, abs=0.05)

    response = client.get(f"/api/renders/{done['id']}/file", params={"download": True})
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    path = tmp_path / "result.mp4"
    path.write_bytes(response.content)
    info = json.loads(
        subprocess.run(
            [
                ffprobe_bin(),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1280, 720)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert float(info["format"]["duration"]) == pytest.approx(expected, abs=0.15)

    assert client.delete(f"/api/renders/{done['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/renders").json() == []


@requires_ffmpeg
def test_render_needs_cuts(tmp_path: Path) -> None:
    project = client.post("/api/projects", json={"name": "빈 프로젝트"}).json()
    assert client.post(f"/api/projects/{project['id']}/renders", json={}).status_code == 409
