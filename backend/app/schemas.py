"""Request and response models for the API."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

TransitionType = Literal["fade", "text_card", "none"]
SelectionSource = Literal["drag", "detect"]
JobStatus = Literal["queued", "running", "done", "failed", "canceled"]


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
    """Boxes in source pixels (after rotation) for the proxy frame at `frame_index`."""

    t: float = Field(ge=0)
    frame_index: int = Field(ge=0)
    boxes: list[DetectionBox]


class TargetIn(BaseModel):
    """The object a clip follows: a box on one frame, in source pixels."""

    model_config = ConfigDict(extra="forbid")

    t: float = Field(ge=0)
    bbox: BBox
    source: SelectionSource
    class_name: str | None = Field(default=None, max_length=64)
    confidence: float | None = Field(default=None, ge=0, le=1)


class Target(TargetIn):
    """Stored target. `t` is snapped to the middle of proxy frame `frame_index`.

    `source` "auto" means it was found by looking for the project's shared target
    (picked in another clip); `score` is how much it looked like it, 0..1.
    """

    source: Literal["drag", "detect", "auto"]  # type: ignore[assignment]
    frame_index: int = Field(ge=0)
    score: float | None = Field(default=None, ge=0, le=1)


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


class JobView(BaseModel):
    id: str
    kind: str
    ref_id: str
    status: JobStatus
    stage: str | None = None
    progress: float = Field(ge=0, le=1)
    message: str | None = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class ProxyState(BaseModel):
    status: JobStatus
    progress: float = Field(ge=0, le=1)
    job_id: str
    error: str | None = None


class VideoView(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    rotation: int = 0
    video_codec: str | None = None
    has_audio: bool = False
    variable_fps: bool = False
    proxy_fps: int = Field(ge=1, description="미리보기 고정 fps. 프레임 = floor(t × proxy_fps)")
    proxy: ProxyState | None = None
    created_at: str


class AnalysisState(BaseModel):
    """Progress of the clip's target analysis. `ready` once its signals can be read."""

    status: JobStatus
    progress: float = Field(ge=0, le=1)
    stage: str | None = None
    job_id: str
    error: str | None = None
    ready: bool = False


class SegmentParams(BaseModel):
    """How to cut a clip. Defaults match app/segments.py Params."""

    model_config = ConfigDict(extra="forbid")

    sensitivity: float = Field(default=1.0, ge=0.25, le=4)
    use_move: bool = True
    use_turn: bool = True
    merge_gap: float = Field(default=0.5, ge=0, le=5)
    padding: float = Field(default=0.3, ge=0, le=3)
    min_length: float = Field(default=1.0, ge=0, le=10)


class SegmentEdit(BaseModel):
    """A manual change, applied in order after the automatic cut."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["keep", "drop"]
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def end_after_start(self) -> SegmentEdit:
        if self.end <= self.start:
            raise ValueError("end는 start보다 커야 합니다.")
        return self


class SegmentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    params: SegmentParams = Field(default_factory=SegmentParams)
    edits: list[SegmentEdit] = Field(default_factory=list, max_length=500)


class Cut(BaseModel):
    """A part of the clip to keep, in clip seconds."""

    start: float
    end: float
    score: float = Field(ge=0, le=1)
    edited: bool = False


class SegmentsView(SegmentSettings):
    cuts: list[Cut]
    duration: float
    kept: float


class ClipView(BaseModel):
    id: str
    project_id: str
    position: int
    video: VideoView
    target: Target | None = None
    analysis: AnalysisState | None = None
    #: Parts to keep, once analysed.
    cuts: list[Cut] | None = None


class ReferenceView(BaseModel):
    """The target picked by hand, shared by every clip of the project."""

    clip_id: str
    class_name: str | None = None


class ProjectView(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    clips: list[ClipView]
    reference: ReferenceView | None = None


class ProjectSummaryView(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    clip_count: int
    total_duration: float
    cover_video_id: str | None = None


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class ProjectUpdate(ProjectCreate):
    pass


class ClipOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_ids: list[str]


class DriveLink(BaseModel):
    web_view_link: str | None = None
    error: str | None = None


class SequenceSettings(BaseModel):
    """Transitions between cuts and title cards for the whole result.

    `overrides` is keyed by the cut a transition follows (`SequenceItem.key`);
    every other gap uses `default`. Intro and outro are text cards or nothing.
    """

    model_config = ConfigDict(extra="forbid")

    default: TransitionAfter = Field(default_factory=lambda: TransitionAfter(type="none"))
    overrides: dict[str, TransitionAfter] = Field(default_factory=dict, max_length=2000)
    intro: TransitionAfter | None = None
    outro: TransitionAfter | None = None

    @model_validator(mode="after")
    def cards_are_text(self) -> SequenceSettings:
        for card in (self.intro, self.outro):
            if card is not None and card.type != "text_card":
                raise ValueError("시작·끝 제목은 text_card여야 합니다.")
        return self


class SequenceItem(BaseModel):
    key: str
    clip_id: str
    video_id: str
    clip_position: int
    index: int
    start: float
    end: float
    #: The transition into the next item; None after the last one.
    transition_after: TransitionAfter | None = None


class SequenceView(SequenceSettings):
    items: list[SequenceItem]
    total: float


class RenderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Literal["source", "1080", "720"] = "1080"
    quality: Literal["small", "mid", "high"] = "mid"
    audio: bool = True


class RenderView(BaseModel):
    id: str
    project_id: str
    settings: RenderSettings
    created_at: str
    status: JobStatus
    progress: float = Field(ge=0, le=1)
    stage: str | None = None
    error: str | None = None
    ready: bool = False
    filename: str
    duration: float | None = None
    size_bytes: int | None = None
