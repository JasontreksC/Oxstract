"""Request and response models for the section 4 / 5.0 / 5.5 API."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

TransitionType = Literal["fade", "text_card", "none"]
SelectionSource = Literal["drag", "detect"]
JobState = Literal[
    "queued",
    "running",
    "awaiting_edit",
    "rendering",
    "uploading",
    "completed",
    "failed",
]
ProgressStage = Literal["detect", "track", "segment", "render", "upload", "done", "error"]


class BBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class DetectionBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bbox: BBox
    class_name: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class DetectResponse(BaseModel):
    t: float = Field(ge=0)
    boxes: list[DetectionBox]


class TransitionAfter(BaseModel):
    """Cut-to-cut transition. Omit it on the last segment."""

    model_config = ConfigDict(extra="forbid")

    type: TransitionType
    duration: float | None = Field(default=None, gt=0)
    bg_color: str | None = None
    text: str | None = None
    font_size: float | None = Field(default=None, gt=0)
    font_color: str | None = None

    @model_validator(mode="after")
    def required_for_type(self) -> TransitionAfter:
        if self.bg_color is not None and not _COLOR.match(self.bg_color):
            raise ValueError("bg_color는 #RRGGBB 형식이어야 합니다.")
        if self.font_color is not None and not _COLOR.match(self.font_color):
            raise ValueError("font_color는 #RRGGBB 형식이어야 합니다.")
        if self.type == "fade" and self.duration is None:
            raise ValueError("fade에는 duration이 필요합니다.")
        if self.type == "text_card":
            missing = [
                name
                for name in ("duration", "bg_color", "text", "font_size", "font_color")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError("text_card에는 " + ", ".join(missing) + "가 필요합니다.")
        return self


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0)
    end: float = Field(gt=0)
    score: float = Field(ge=0, le=1)
    transition_after: TransitionAfter | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> Segment:
        if self.end <= self.start:
            raise ValueError("end는 start보다 커야 합니다.")
        return self


class SegmentList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segments: list[Segment]

    @model_validator(mode="after")
    def last_segment_has_no_transition(self) -> SegmentList:
        if self.segments and self.segments[-1].transition_after is not None:
            raise ValueError("마지막 구간에는 transition_after를 둘 수 없습니다.")
        return self


class JobOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motion_threshold: float = Field(default=0.05, ge=0)
    min_segment_duration: float = Field(default=1.0, gt=0)
    padding: float = Field(default=0.3, ge=0)
    include_audio: bool = True


class JobTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    class_name: str | None = None


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    video_id: str = Field(min_length=1)
    frame_t: float = Field(ge=0)
    bbox: BBox
    source: SelectionSource
    class_name: str | None = Field(default=None, alias="class")
    target: JobTarget | None = None
    options: JobOptions = Field(default_factory=JobOptions)


class VideoCreated(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None


class DriveLink(BaseModel):
    web_view_link: str | None = None
    error: str | None = None


class JobView(BaseModel):
    id: str
    video_id: str
    status: JobState
    progress: float = Field(ge=0, le=1)
    segments: list[Segment]
    error: str | None = None
    output_ready: bool = False
    drive: DriveLink | None = None


class RenderAccepted(BaseModel):
    job_id: str
    status: Literal["rendering"]


class ProgressEvent(BaseModel):
    job_id: str
    stage: ProgressStage
    progress: float = Field(ge=0, le=1)
    message: str = ""
    drive: DriveLink | None = None
