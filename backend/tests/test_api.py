import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.main import app
from app.schemas import SegmentList

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]

PATHS = [
    "/videos",
    "/videos/{video_id}/frame",
    "/videos/{video_id}/detect",
    "/jobs",
    "/jobs/{job_id}",
    "/jobs/{job_id}/segments",
    "/jobs/{job_id}/render",
    "/jobs/{job_id}/output",
]


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_plan_routes() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in PATHS:
        assert path in paths
    websocket_paths = [getattr(route, "path", None) for route in app.routes]
    assert "/jobs/{job_id}/progress" in websocket_paths


def test_upload_is_stub() -> None:
    response = client.post(
        "/videos",
        files={"file": ("clip.mp4", b"not-a-video", "video/mp4")},
    )
    assert response.status_code == 501


def test_create_job_rejects_unknown_source() -> None:
    response = client.post(
        "/jobs",
        json={
            "video_id": "v1",
            "frame_t": 1.0,
            "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
            "source": "text",
        },
    )
    assert response.status_code == 422


def test_create_job_accepts_plan_body_then_stubs() -> None:
    response = client.post(
        "/jobs",
        json={
            "video_id": "v1",
            "frame_t": 1.25,
            "bbox": {"x": 1, "y": 2, "width": 10, "height": 20},
            "source": "detect",
            "class": "dog",
            "target": {"text": "강아지"},
            "options": {"motion_threshold": 0.05, "min_segment_duration": 1, "padding": 0.3},
        },
    )
    assert response.status_code == 501


def test_patch_segments_validates_then_stubs() -> None:
    response = client.patch(
        "/jobs/job-1/segments",
        json={
            "segments": [
                {
                    "start": 1.2,
                    "end": 4.8,
                    "score": 0.8,
                    "transition_after": {"type": "fade", "duration": 0.5},
                },
                {"start": 12, "end": 15, "score": 0.4},
            ]
        },
    )
    assert response.status_code == 501


def test_patch_rejects_transition_on_last_segment() -> None:
    with pytest.raises(ValidationError):
        SegmentList.model_validate(
            {
                "segments": [
                    {
                        "start": 0,
                        "end": 1,
                        "score": 1,
                        "transition_after": {"type": "none"},
                    }
                ]
            }
        )
    response = client.patch(
        "/jobs/job-1/segments",
        json={
            "segments": [
                {
                    "start": 0,
                    "end": 1,
                    "score": 1,
                    "transition_after": {"type": "none"},
                }
            ]
        },
    )
    assert response.status_code == 422


def test_output_missing() -> None:
    response = client.get("/jobs/missing/output")
    assert response.status_code == 404


def test_progress_socket_stub() -> None:
    with client.websocket_connect("/jobs/job-1/progress") as socket:
        payload = socket.receive_json()
    assert payload["job_id"] == "job-1"
    assert payload["stage"] == "error"


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
