import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app import jobs
from app.db import transaction
from app.main import app, create_app
from app.schemas import SegmentList

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]

PATHS = [
    "/api/health",
    "/api/projects",
    "/api/projects/{project_id}",
    "/api/projects/{project_id}/clips",
    "/api/projects/{project_id}/clips/{clip_id}",
    "/api/projects/{project_id}/clips/order",
    "/api/projects/{project_id}/clips/{clip_id}/target",
    "/api/videos/{video_id}",
    "/api/videos/{video_id}/file",
    "/api/videos/{video_id}/proxy",
    "/api/videos/{video_id}/frame",
    "/api/videos/{video_id}/thumb",
    "/api/videos/{video_id}/detect",
    "/api/jobs",
    "/api/jobs/{job_id}",
    "/api/jobs/{job_id}/cancel",
    "/api/jobs/{job_id}/events",
]


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_routes() -> None:
    paths = client.get("/api/openapi.json").json()["paths"]
    for path in PATHS:
        assert path in paths


def test_detect_unknown_video_is_404() -> None:
    assert client.post("/api/videos/v1/detect", params={"t": 1}).status_code == 404


def test_job_events_stream_until_finished() -> None:
    with transaction() as conn:
        job_id = jobs.enqueue(conn, "proxy", "video-1")
    jobs.finish(job_id)

    response = client.get(f"/api/jobs/{job_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert len(events) == 1
    assert json.loads(events[0][len("data: ") :])["status"] == "done"


def test_job_events_unknown_job_is_404() -> None:
    assert client.get("/api/jobs/missing/events").status_code == 404


def test_cancel_queued_job() -> None:
    with transaction() as conn:
        job_id = jobs.enqueue(conn, "proxy", "video-1")

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert client.get("/api/jobs", params={"active": True}).json() == []


def test_spa_serves_index_for_app_routes(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Oxstract</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg></svg>")
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    spa = TestClient(create_app())

    assert "Oxstract" in spa.get("/").text
    assert "Oxstract" in spa.get("/p/abc/segments").text
    assert spa.get("/assets/app.js").text == "console.log(1)"
    assert spa.get("/favicon.svg").text == "<svg></svg>"
    assert spa.get("/api/nope").status_code == 404
    assert spa.get("/api/health").json() == {"status": "ok"}
    assert "Oxstract" in spa.get("/../../etc/passwd").text


def test_segment_list_rejects_transition_on_last_segment() -> None:
    with pytest.raises(ValidationError):
        SegmentList.model_validate(
            {"segments": [{"start": 0, "end": 1, "score": 1, "transition_after": {"type": "none"}}]}
        )


def _schema_registry() -> Registry:
    resources = []
    for name in ("transition.schema.json", "segment.schema.json", "segment-list.schema.json"):
        contents = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
        resources.append(
            (contents["$id"], Resource.from_contents(contents, default_specification=DRAFT202012))
        )
    return Registry().with_resources(resources)


def test_segment_list_schema_accepts_transitions() -> None:
    registry = _schema_registry()
    contents = json.loads(
        (ROOT / "schemas" / "segment-list.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(contents, registry=registry)
    validator.validate(
        {
            "segments": [
                {
                    "start": 1.2,
                    "end": 4.8,
                    "score": 0.86,
                    "transition_after": {"type": "fade", "duration": 0.5},
                },
                {
                    "start": 12.0,
                    "end": 15.5,
                    "score": 0.74,
                    "transition_after": {
                        "type": "text_card",
                        "duration": 2,
                        "bg_color": "#111111",
                        "text": "다음 장면",
                        "font_size": 48,
                        "font_color": "#FFFFFF",
                    },
                },
                {"start": 20, "end": 22, "score": 0.5, "transition_after": None},
            ]
        }
    )


def test_transition_schema_rejects_fade_without_duration() -> None:
    registry = _schema_registry()
    contents = json.loads((ROOT / "schemas" / "transition.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(contents, registry=registry)
    errors = list(validator.iter_errors({"type": "fade"}))
    assert errors
