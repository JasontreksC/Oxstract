"""The result's running order: clips in order, each clip's kept parts in time order.

Transitions are stored per project, keyed by the cut they follow (clip id plus
the cut's start to a tenth of a second), so recutting one clip leaves the other
clips' transitions where they were. Gaps without an override use the default.
"""

from __future__ import annotations

from app import store
from app.render import Card, Piece
from app.schemas import SequenceItem, SequenceSettings, TransitionAfter


def cut_key(clip_id: str, start: float) -> str:
    return f"{clip_id}:{start:.1f}"


def settings_of(project: store.ProjectRecord) -> SequenceSettings:
    return SequenceSettings.model_validate(project.sequence or {})


def items(project: store.ProjectRecord, settings: SequenceSettings) -> list[SequenceItem]:
    result: list[SequenceItem] = []
    for clip in project.clips:
        if not clip.analysis_path or not clip.cuts:
            continue
        for index, cut in enumerate(clip.cuts):
            key = cut_key(clip.id, cut["start"])
            result.append(
                SequenceItem(
                    key=key,
                    clip_id=clip.id,
                    video_id=clip.video.id,
                    clip_position=clip.position,
                    index=index,
                    start=cut["start"],
                    end=cut["end"],
                    transition_after=settings.overrides.get(key, settings.default),
                )
            )
    if result:
        result[-1].transition_after = None
    return result


def _card(transition: TransitionAfter) -> Card:
    return Card(
        text=transition.text or "",
        duration=transition.duration or 2.0,
        bg_color=transition.bg_color or "#111111",
        font_color=transition.font_color or "#FFFFFF",
        font_size=transition.font_size or 48,
    )


def total_seconds(sequence: list[SequenceItem], settings: SequenceSettings) -> float:
    total = sum(item.end - item.start for item in sequence)
    total += sum(
        item.transition_after.duration or 0
        for item in sequence
        if item.transition_after is not None and item.transition_after.type == "text_card"
    )
    for card in (settings.intro, settings.outro):
        if card is not None:
            total += card.duration or 0
    return round(total, 3)


def pieces(project: store.ProjectRecord, settings: SequenceSettings) -> list[Piece]:
    """What app/render.py encodes, in order. Fades sit inside the cuts on both sides."""

    clips = {clip.id: clip for clip in project.clips}
    sequence = items(project, settings)
    result: list[Piece] = []
    if settings.intro is not None:
        result.append(Piece(duration=settings.intro.duration or 2.0, card=_card(settings.intro)))
    fade_in = 0.0
    for position, item in enumerate(sequence):
        clip = clips[item.clip_id]
        length = item.end - item.start
        after = item.transition_after
        fade_out = 0.0
        if after is not None and after.type == "fade":
            following = sequence[position + 1]
            limit = min(length, following.end - following.start) / 2
            fade_out = min(after.duration or 0.5, limit)
        result.append(
            Piece(
                duration=length,
                source=clip.video.path,
                start=item.start,
                has_audio=clip.video.has_audio,
                fade_in=min(fade_in, length / 2),
                fade_out=fade_out,
            )
        )
        fade_in = fade_out
        if after is not None and after.type == "text_card":
            result.append(Piece(duration=after.duration or 2.0, card=_card(after)))
    if settings.outro is not None:
        result.append(Piece(duration=settings.outro.duration or 2.0, card=_card(settings.outro)))
    return result
