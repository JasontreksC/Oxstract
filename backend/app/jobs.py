"""Job queue kept in the SQLite `jobs` table.

One worker process claims queued jobs in creation order and writes progress back.
The API reads the same rows to show status. A running job that the worker leaves
behind (crash, restart) is marked failed when the next worker starts.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from app.db import session, transaction

TERMINAL = ("done", "failed", "canceled")

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"
_COLUMNS = (
    "id, kind, ref_id, status, stage, progress, message, error, cancel_requested,"
    " created_at, started_at, finished_at"
)


@dataclass(frozen=True)
class JobRecord:
    id: str
    kind: str
    ref_id: str
    status: str
    stage: str | None
    progress: float
    message: str | None
    error: str | None
    cancel_requested: bool
    created_at: str
    started_at: str | None
    finished_at: str | None


def _record(row: sqlite3.Row) -> JobRecord:
    values = dict(row)
    values["cancel_requested"] = bool(values["cancel_requested"])
    return JobRecord(**values)


def enqueue(conn: sqlite3.Connection, kind: str, ref_id: str) -> str:
    """Insert a queued job on an open connection so callers can share a transaction."""

    job_id = uuid.uuid4().hex
    conn.execute("INSERT INTO jobs (id, kind, ref_id) VALUES (?, ?, ?)", (job_id, kind, ref_id))
    return job_id


def get_job(job_id: str) -> JobRecord | None:
    with session() as conn:
        row = conn.execute(f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _record(row) if row else None


def list_jobs(*, active_only: bool = False) -> list[JobRecord]:
    where = "WHERE status IN ('queued', 'running')" if active_only else ""
    with session() as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM jobs {where} ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    return [_record(row) for row in rows]


def claim_next() -> JobRecord | None:
    with transaction() as conn:
        row = conn.execute(
            f"UPDATE jobs SET status = 'running', started_at = {_NOW}"
            " WHERE id = (SELECT id FROM jobs WHERE status = 'queued'"
            " ORDER BY created_at, rowid LIMIT 1)"
            f" RETURNING {_COLUMNS}"
        ).fetchone()
    return _record(row) if row else None


def report(
    job_id: str, progress: float, stage: str | None = None, message: str | None = None
) -> bool:
    """Store progress. Return False when the job was asked to stop."""

    with session() as conn:
        row = conn.execute(
            "UPDATE jobs SET progress = ?, stage = COALESCE(?, stage),"
            " message = COALESCE(?, message) WHERE id = ? RETURNING cancel_requested",
            (max(0.0, min(1.0, progress)), stage, message, job_id),
        ).fetchone()
    return row is not None and not row[0]


def _finish(job_id: str, status: str, error: str | None = None) -> None:
    progress = "1" if status == "done" else "progress"
    with session() as conn:
        conn.execute(
            f"UPDATE jobs SET status = ?, error = ?, progress = {progress}, finished_at = {_NOW}"
            " WHERE id = ?",
            (status, error, job_id),
        )


def finish(job_id: str) -> None:
    _finish(job_id, "done")


def fail(job_id: str, error: str) -> None:
    _finish(job_id, "failed", error)


def mark_canceled(job_id: str) -> None:
    _finish(job_id, "canceled")


def request_cancel(job_id: str) -> JobRecord | None:
    """Cancel a queued job at once, or flag a running one for the worker to stop."""

    with transaction() as conn:
        conn.execute(
            f"UPDATE jobs SET status = 'canceled', finished_at = {_NOW}"
            " WHERE id = ? AND status = 'queued'",
            (job_id,),
        )
        conn.execute(
            "UPDATE jobs SET cancel_requested = 1 WHERE id = ? AND status = 'running'", (job_id,)
        )
    return get_job(job_id)


def recover_stale() -> int:
    """Fail jobs a previous worker left running. Return how many were reset."""

    with session() as conn:
        cursor = conn.execute(
            f"UPDATE jobs SET status = 'failed', error = ?, finished_at = {_NOW}"
            " WHERE status = 'running'",
            ("워커가 다시 시작되어 작업이 중단되었습니다. 다시 시도하세요.",),
        )
    return cursor.rowcount
