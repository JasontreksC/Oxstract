"""Videos, projects, and ordered clips in SQLite. Files live under MEDIA_ROOT."""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from app import jobs
from app.db import media_root, session, transaction
from app.media import ProbeResult

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"
_VIDEO_COLUMNS = (
    "id, filename, content_type, path, duration, width, height, fps, rotation, video_codec,"
    " has_audio, variable_fps, proxy_path, proxy_job_id, created_at"
)


class NotFound(LookupError):
    pass


class InvalidOrder(ValueError):
    pass


class MissingTarget(ValueError):
    pass


@dataclass(frozen=True)
class VideoRecord:
    id: str
    filename: str
    content_type: str | None
    path: str
    duration: float | None
    width: int | None
    height: int | None
    fps: float | None
    rotation: int
    video_codec: str | None
    has_audio: bool
    variable_fps: bool
    proxy_path: str | None
    proxy_job_id: str | None
    created_at: str

    @property
    def playable_path(self) -> str:
        """The proxy when it exists, otherwise the original."""

        if self.proxy_path and Path(self.proxy_path).is_file():
            return self.proxy_path
        return self.path


@dataclass(frozen=True)
class ClipRecord:
    id: str
    project_id: str
    position: int
    video: VideoRecord
    target: dict | None = None
    analysis_job_id: str | None = None
    analysis_path: str | None = None
    segment_params: dict | None = None
    segment_edits: list | None = None
    cuts: list | None = None


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str
    created_at: str
    updated_at: str
    clips: list[ClipRecord]
    sequence: dict | None = None
    reference: dict | None = None


@dataclass(frozen=True)
class RenderRecord:
    id: str
    project_id: str
    job_id: str
    settings: dict
    path: str | None
    filename: str
    duration: float | None
    size_bytes: int | None
    created_at: str


@dataclass(frozen=True)
class ProjectSummary:
    id: str
    name: str
    created_at: str
    updated_at: str
    clip_count: int
    total_duration: float
    cover_video_id: str | None


def video_dir(video_id: str) -> Path:
    return media_root() / "videos" / video_id


def clip_dir(clip_id: str) -> Path:
    return media_root() / "clips" / clip_id


def render_dir(render_id: str) -> Path:
    return media_root() / "renders" / render_id


def reference_image(project_id: str) -> Path:
    """What the shared target looks like: its crop from the frame it was picked in."""

    return media_root() / "projects" / project_id / "reference.png"


def _cancel_jobs(conn: sqlite3.Connection, ref_id: str) -> None:
    """Cancel queued jobs for `ref_id` and ask running ones to stop."""

    conn.execute(
        "UPDATE jobs SET cancel_requested = 1 WHERE ref_id = ? AND status = 'running'", (ref_id,)
    )
    conn.execute(
        f"UPDATE jobs SET status = 'canceled', finished_at = {_NOW}"
        " WHERE ref_id = ? AND status = 'queued'",
        (ref_id,),
    )


def _video(row: sqlite3.Row) -> VideoRecord:
    values = dict(row)
    values["has_audio"] = bool(values["has_audio"])
    values["variable_fps"] = bool(values["variable_fps"])
    return VideoRecord(**values)


def _get_video(conn: sqlite3.Connection, video_id: str) -> VideoRecord | None:
    row = conn.execute(f"SELECT {_VIDEO_COLUMNS} FROM videos WHERE id = ?", (video_id,)).fetchone()
    return _video(row) if row else None


def get_video(video_id: str) -> VideoRecord | None:
    with session() as conn:
        return _get_video(conn, video_id)


def list_videos() -> list[VideoRecord]:
    with session() as conn:
        rows = conn.execute(f"SELECT {_VIDEO_COLUMNS} FROM videos ORDER BY created_at").fetchall()
    return [_video(row) for row in rows]


def _insert_video(
    conn: sqlite3.Connection,
    video_id: str,
    filename: str,
    content_type: str | None,
    path: Path,
    info: ProbeResult,
) -> None:
    job_id = jobs.enqueue(conn, "proxy", video_id)
    conn.execute(
        "INSERT INTO videos (id, filename, content_type, path, duration, width, height, fps,"
        " rotation, video_codec, has_audio, variable_fps, proxy_job_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            video_id,
            filename,
            content_type,
            str(path),
            info.duration,
            info.width,
            info.height,
            info.fps,
            info.rotation,
            info.video_codec,
            int(info.has_audio),
            int(info.variable_fps),
            job_id,
        ),
    )


def queue_proxy(video_id: str) -> str:
    """Queue a fresh proxy job, for example after a failure. Return its id."""

    with transaction() as conn:
        if _get_video(conn, video_id) is None:
            raise NotFound(video_id)
        job_id = jobs.enqueue(conn, "proxy", video_id)
        conn.execute(
            "UPDATE videos SET proxy_job_id = ?, proxy_path = NULL WHERE id = ?",
            (job_id, video_id),
        )
    return job_id


def set_proxy_path(video_id: str, path: Path) -> None:
    with session() as conn:
        conn.execute("UPDATE videos SET proxy_path = ? WHERE id = ?", (str(path), video_id))


def _delete_video_files(video_ids: list[str]) -> None:
    for video_id in video_ids:
        shutil.rmtree(video_dir(video_id), ignore_errors=True)


def _drop_unused_videos(conn: sqlite3.Connection, video_ids: list[str]) -> list[str]:
    """Delete rows of the given videos that no clip uses any more. Return their ids."""

    dropped = []
    for video_id in video_ids:
        used = conn.execute(
            "SELECT 1 FROM clips WHERE video_id = ? LIMIT 1", (video_id,)
        ).fetchone()
        if used:
            continue
        _cancel_jobs(conn, video_id)
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        dropped.append(video_id)
    return dropped


# Projects


def create_project(name: str) -> ProjectRecord:
    project_id = uuid.uuid4().hex
    with session() as conn:
        conn.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (project_id, name))
    project = get_project(project_id)
    assert project is not None
    return project


def list_projects() -> list[ProjectSummary]:
    with session() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   COUNT(c.id) AS clip_count,
                   COALESCE(SUM(v.duration), 0) AS total_duration,
                   (SELECT c2.video_id FROM clips c2 WHERE c2.project_id = p.id
                    ORDER BY c2.position LIMIT 1) AS cover_video_id
            FROM projects p
            LEFT JOIN clips c ON c.project_id = p.id
            LEFT JOIN videos v ON v.id = c.video_id
            GROUP BY p.id
            ORDER BY p.updated_at DESC
            """
        ).fetchall()
    return [ProjectSummary(**dict(row)) for row in rows]


def _get_project(conn: sqlite3.Connection, project_id: str) -> ProjectRecord | None:
    row = conn.execute(
        "SELECT id, name, created_at, updated_at, sequence, reference FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    video_columns = ", ".join(f"v.{name.strip()}" for name in _VIDEO_COLUMNS.split(","))
    clip_rows = conn.execute(
        "SELECT c.id AS clip_id, c.position, c.target AS clip_target,"
        " c.analysis_job_id AS clip_analysis_job_id, c.analysis_path AS clip_analysis_path,"
        " c.segment_params AS clip_segment_params, c.segment_edits AS clip_segment_edits,"
        f" c.cuts AS clip_cuts, {video_columns} FROM clips c"
        " JOIN videos v ON v.id = c.video_id WHERE c.project_id = ? ORDER BY c.position",
        (project_id,),
    ).fetchall()
    clips = []
    for clip_row in clip_rows:
        values = dict(clip_row)
        clip_id = values.pop("clip_id")
        position = values.pop("position")
        target = values.pop("clip_target")
        analysis_job_id = values.pop("clip_analysis_job_id")
        analysis_path = values.pop("clip_analysis_path")
        params, edits, cuts = (
            values.pop(f"clip_{key}") for key in ("segment_params", "segment_edits", "cuts")
        )
        clips.append(
            ClipRecord(
                id=clip_id,
                project_id=project_id,
                position=position,
                video=_video(values),
                target=json.loads(target) if target else None,
                analysis_job_id=analysis_job_id,
                analysis_path=analysis_path,
                segment_params=json.loads(params) if params else None,
                segment_edits=json.loads(edits) if edits else None,
                cuts=json.loads(cuts) if cuts else None,
            )
        )
    values = dict(row)
    sequence, reference = values.pop("sequence"), values.pop("reference")
    return ProjectRecord(
        clips=clips,
        sequence=json.loads(sequence) if sequence else None,
        reference=json.loads(reference) if reference else None,
        **values,
    )


def get_project(project_id: str) -> ProjectRecord | None:
    with session() as conn:
        return _get_project(conn, project_id)


def _touch(conn: sqlite3.Connection, project_id: str) -> None:
    conn.execute(f"UPDATE projects SET updated_at = {_NOW} WHERE id = ?", (project_id,))


def rename_project(project_id: str, name: str) -> ProjectRecord:
    with session() as conn:
        cursor = conn.execute(
            f"UPDATE projects SET name = ?, updated_at = {_NOW} WHERE id = ?", (name, project_id)
        )
        if cursor.rowcount == 0:
            raise NotFound(project_id)
        project = _get_project(conn, project_id)
    assert project is not None
    return project


def delete_project(project_id: str) -> None:
    """Delete the project, its clips, and any of their videos no other project uses."""

    with transaction() as conn:
        if _get_project(conn, project_id) is None:
            raise NotFound(project_id)
        rows = conn.execute(
            "SELECT id, video_id FROM clips WHERE project_id = ?", (project_id,)
        ).fetchall()
        for clip_id, _ in rows:
            _cancel_jobs(conn, clip_id)
        renders = conn.execute(
            "SELECT id, job_id FROM renders WHERE project_id = ?", (project_id,)
        ).fetchall()
        for _, job_id in renders:
            conn.execute(
                "UPDATE jobs SET cancel_requested = 1 WHERE id = ? AND status = 'running'",
                (job_id,),
            )
            conn.execute(
                f"UPDATE jobs SET status = 'canceled', finished_at = {_NOW}"
                " WHERE id = ? AND status = 'queued'",
                (job_id,),
            )
        conn.execute("DELETE FROM renders WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM clips WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        dropped = _drop_unused_videos(conn, sorted({video_id for _, video_id in rows}))
    _delete_video_files(dropped)
    for clip_id, _ in rows:
        shutil.rmtree(clip_dir(clip_id), ignore_errors=True)
    for render_id, _ in renders:
        shutil.rmtree(render_dir(render_id), ignore_errors=True)


# Clips


def add_clip(
    project_id: str,
    *,
    video_id: str,
    filename: str,
    content_type: str | None,
    path: Path,
    info: ProbeResult,
) -> ClipRecord:
    """Store an uploaded video and append it to the project as a clip."""

    clip_id = uuid.uuid4().hex
    with transaction() as conn:
        if _get_project(conn, project_id) is None:
            raise NotFound(project_id)
        _insert_video(conn, video_id, filename, content_type, path, info)
        position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM clips WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO clips (id, project_id, video_id, position) VALUES (?, ?, ?, ?)",
            (clip_id, project_id, video_id, position),
        )
        reference = conn.execute(
            "SELECT reference FROM projects WHERE id = ?", (project_id,)
        ).fetchone()[0]
        if reference:
            # Queued after the proxy job, so the proxy exists when it runs.
            job_id = jobs.enqueue(conn, "analyze", clip_id)
            conn.execute("UPDATE clips SET analysis_job_id = ? WHERE id = ?", (job_id, clip_id))
        _touch(conn, project_id)
        video = _get_video(conn, video_id)
    assert video is not None
    return ClipRecord(id=clip_id, project_id=project_id, position=position, video=video)


def remove_clip(project_id: str, clip_id: str) -> None:
    with transaction() as conn:
        row = conn.execute(
            "SELECT video_id FROM clips WHERE id = ? AND project_id = ?", (clip_id, project_id)
        ).fetchone()
        if row is None:
            raise NotFound(clip_id)
        _cancel_jobs(conn, clip_id)
        conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
        remaining = conn.execute(
            "SELECT id FROM clips WHERE project_id = ? ORDER BY position", (project_id,)
        ).fetchall()
        for position, (remaining_id,) in enumerate(remaining):
            conn.execute("UPDATE clips SET position = ? WHERE id = ?", (position, remaining_id))
        _touch(conn, project_id)
        dropped = _drop_unused_videos(conn, [row[0]])
    _delete_video_files(dropped)
    shutil.rmtree(clip_dir(clip_id), ignore_errors=True)


def get_clip(project_id: str, clip_id: str) -> ClipRecord | None:
    project = get_project(project_id)
    if project is None:
        return None
    return next((clip for clip in project.clips if clip.id == clip_id), None)


def get_clip_by_id(clip_id: str) -> ClipRecord | None:
    with session() as conn:
        row = conn.execute("SELECT project_id FROM clips WHERE id = ?", (clip_id,)).fetchone()
    return get_clip(row[0], clip_id) if row else None


def set_target(
    project_id: str, clip_id: str, target: dict | None, *, analyse: bool | None = None
) -> ClipRecord:
    """Store or clear the object the clip follows. A new target starts a fresh analysis;
    `analyse=True` also starts one without a target (to find the shared target)."""

    with transaction() as conn:
        row = conn.execute(
            "SELECT analysis_path FROM clips WHERE id = ? AND project_id = ?",
            (clip_id, project_id),
        ).fetchone()
        if row is None:
            raise NotFound(clip_id)
        _cancel_jobs(conn, clip_id)
        if analyse is None:
            analyse = target is not None
        job_id = jobs.enqueue(conn, "analyze", clip_id) if analyse else None
        conn.execute(
            "UPDATE clips SET target = ?, analysis_job_id = ?, analysis_path = NULL, cuts = NULL"
            " WHERE id = ?",
            (json.dumps(target) if target is not None else None, job_id, clip_id),
        )
        _touch(conn, project_id)
    if row[0]:
        Path(row[0]).unlink(missing_ok=True)
    clip = get_clip(project_id, clip_id)
    assert clip is not None
    return clip


def queue_analysis(project_id: str, clip_id: str) -> ClipRecord:
    """Analyse the clip again, for example after a failure. Without a target of its
    own the clip looks for the project's shared target first."""

    project = get_project(project_id)
    clip = get_clip(project_id, clip_id)
    if project is None or clip is None:
        raise NotFound(clip_id)
    shared = project.reference
    if clip.target is None and (not shared or shared.get("clip_id") == clip_id):
        raise MissingTarget("대상을 먼저 지정하세요.")
    return set_target(project_id, clip_id, clip.target, analyse=True)


def share_target(project_id: str, clip_id: str, class_name: str | None) -> list[str]:
    """Make the clip's target the project's shared one, and look for it again in every
    clip whose target was found automatically or is missing. Return those clip ids."""

    relocated = []
    with transaction() as conn:
        conn.execute(
            "UPDATE projects SET reference = ? WHERE id = ?",
            (json.dumps({"clip_id": clip_id, "class_name": class_name}), project_id),
        )
        rows = conn.execute(
            "SELECT id, target, analysis_path FROM clips WHERE project_id = ? AND id != ?",
            (project_id, clip_id),
        ).fetchall()
        for other_id, target, analysis_path in rows:
            if target and json.loads(target).get("source") != "auto":
                continue  # picked by hand in that clip; keep it
            _cancel_jobs(conn, other_id)
            job_id = jobs.enqueue(conn, "analyze", other_id)
            conn.execute(
                "UPDATE clips SET target = NULL, analysis_job_id = ?, analysis_path = NULL,"
                " cuts = NULL WHERE id = ?",
                (job_id, other_id),
            )
            if analysis_path:
                Path(analysis_path).unlink(missing_ok=True)
            relocated.append(other_id)
    return relocated


def forget_shared_target(project_id: str, clip_id: str) -> None:
    """Drop the project's shared target if it was picked in this clip."""

    with session() as conn:
        cursor = conn.execute(
            "UPDATE projects SET reference = NULL"
            " WHERE id = ? AND json_extract(reference, '$.clip_id') = ?",
            (project_id, clip_id),
        )
    if cursor.rowcount:
        reference_image(project_id).unlink(missing_ok=True)


def set_found_target(clip_id: str, job_id: str, target: dict) -> bool:
    """Store a target found automatically, unless a newer job owns the clip."""

    with session() as conn:
        cursor = conn.execute(
            "UPDATE clips SET target = ? WHERE id = ? AND analysis_job_id = ?",
            (json.dumps(target), clip_id, job_id),
        )
    return cursor.rowcount == 1


def set_analysis_result(clip_id: str, job_id: str, path: Path, cuts: list[dict]) -> bool:
    """Record finished signals and their first cut, unless the target changed meanwhile."""

    with session() as conn:
        cursor = conn.execute(
            "UPDATE clips SET analysis_path = ?, cuts = ? WHERE id = ? AND analysis_job_id = ?",
            (str(path), json.dumps(cuts), clip_id, job_id),
        )
    return cursor.rowcount == 1


def set_segments(
    project_id: str, clip_id: str, params: dict, edits: list[dict], cuts: list[dict]
) -> ClipRecord:
    """Store how to cut the clip and the parts that gives."""

    with session() as conn:
        cursor = conn.execute(
            "UPDATE clips SET segment_params = ?, segment_edits = ?, cuts = ?"
            " WHERE id = ? AND project_id = ?",
            (json.dumps(params), json.dumps(edits), json.dumps(cuts), clip_id, project_id),
        )
        if cursor.rowcount == 0:
            raise NotFound(clip_id)
        _touch(conn, project_id)
    clip = get_clip(project_id, clip_id)
    assert clip is not None
    return clip


def reorder_clips(project_id: str, clip_ids: list[str]) -> ProjectRecord:
    with transaction() as conn:
        project = _get_project(conn, project_id)
        if project is None:
            raise NotFound(project_id)
        current = sorted(clip.id for clip in project.clips)
        if sorted(clip_ids) != current or len(set(clip_ids)) != len(clip_ids):
            raise InvalidOrder("clip_ids는 이 프로젝트의 클립을 한 번씩 모두 담아야 합니다.")
        for position, clip_id in enumerate(clip_ids):
            conn.execute("UPDATE clips SET position = ? WHERE id = ?", (position, clip_id))
        _touch(conn, project_id)
        updated = _get_project(conn, project_id)
    assert updated is not None
    return updated


# Sequence and renders


def set_sequence(project_id: str, sequence: dict) -> ProjectRecord:
    with session() as conn:
        cursor = conn.execute(
            f"UPDATE projects SET sequence = ?, updated_at = {_NOW} WHERE id = ?",
            (json.dumps(sequence), project_id),
        )
        if cursor.rowcount == 0:
            raise NotFound(project_id)
    project = get_project(project_id)
    assert project is not None
    return project


_RENDER_COLUMNS = (
    "id, project_id, job_id, settings, path, filename, duration, size_bytes, created_at"
)


def _render(row: sqlite3.Row) -> RenderRecord:
    values = dict(row)
    values["settings"] = json.loads(values["settings"])
    return RenderRecord(**values)


def create_render(project_id: str, settings: dict, filename: str) -> RenderRecord:
    render_id = uuid.uuid4().hex
    with transaction() as conn:
        if _get_project(conn, project_id) is None:
            raise NotFound(project_id)
        job_id = jobs.enqueue(conn, "render", render_id)
        conn.execute(
            "INSERT INTO renders (id, project_id, job_id, settings, filename)"
            " VALUES (?, ?, ?, ?, ?)",
            (render_id, project_id, job_id, json.dumps(settings), filename),
        )
    render = get_render(render_id)
    assert render is not None
    return render


def get_render(render_id: str) -> RenderRecord | None:
    with session() as conn:
        row = conn.execute(
            f"SELECT {_RENDER_COLUMNS} FROM renders WHERE id = ?", (render_id,)
        ).fetchone()
    return _render(row) if row else None


def list_renders(project_id: str) -> list[RenderRecord]:
    with session() as conn:
        rows = conn.execute(
            f"SELECT {_RENDER_COLUMNS} FROM renders WHERE project_id = ?"
            " ORDER BY created_at DESC LIMIT 50",
            (project_id,),
        ).fetchall()
    return [_render(row) for row in rows]


def set_render_result(render_id: str, path: Path, duration: float) -> None:
    with session() as conn:
        conn.execute(
            "UPDATE renders SET path = ?, duration = ?, size_bytes = ? WHERE id = ?",
            (str(path), duration, path.stat().st_size, render_id),
        )


def delete_render(render_id: str) -> None:
    with session() as conn:
        row = conn.execute("SELECT job_id FROM renders WHERE id = ?", (render_id,)).fetchone()
        if row is None:
            raise NotFound(render_id)
        _cancel_jobs(conn, render_id)
        conn.execute("DELETE FROM renders WHERE id = ?", (render_id,))
    shutil.rmtree(render_dir(render_id), ignore_errors=True)
