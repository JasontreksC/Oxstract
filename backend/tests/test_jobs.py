"""SQLite job queue: claim order, progress, cancel, crash recovery, migrations."""

from __future__ import annotations

import sqlite3

from app import jobs
from app.db import SCHEMA_VERSION, media_root, session, transaction


def _enqueue(ref_id: str, kind: str = "proxy") -> str:
    with transaction() as conn:
        return jobs.enqueue(conn, kind, ref_id)


def test_claims_in_creation_order() -> None:
    first = _enqueue("a")
    second = _enqueue("b")

    claimed = jobs.claim_next()

    assert claimed is not None and claimed.id == first
    assert claimed.status == "running"
    assert claimed.started_at is not None
    assert jobs.claim_next().id == second  # type: ignore[union-attr]
    assert jobs.claim_next() is None


def test_report_and_finish() -> None:
    job_id = _enqueue("a")
    jobs.claim_next()

    assert jobs.report(job_id, 0.4, "transcode", "진행 중") is True
    job = jobs.get_job(job_id)
    assert job is not None and job.progress == 0.4 and job.stage == "transcode"

    jobs.finish(job_id)
    done = jobs.get_job(job_id)
    assert done is not None and done.status == "done" and done.progress == 1


def test_cancel_running_job_is_seen_by_report() -> None:
    job_id = _enqueue("a")
    jobs.claim_next()

    flagged = jobs.request_cancel(job_id)

    assert flagged is not None and flagged.status == "running"
    assert jobs.report(job_id, 0.5) is False


def test_recover_stale_fails_running_jobs() -> None:
    job_id = _enqueue("a")
    queued = _enqueue("b")
    jobs.claim_next()

    assert jobs.recover_stale() == 1
    failed = jobs.get_job(job_id)
    assert failed is not None and failed.status == "failed" and failed.error
    assert jobs.get_job(queued).status == "queued"  # type: ignore[union-attr]


def test_list_active_only() -> None:
    running = _enqueue("a")
    _enqueue("b")
    jobs.claim_next()
    jobs.finish(running)

    active = jobs.list_jobs(active_only=True)

    assert [job.ref_id for job in active] == ["b"]


def test_m1_database_is_migrated_and_gets_proxy_jobs() -> None:
    root = media_root()
    root.mkdir(parents=True)
    legacy = sqlite3.connect(root / "oxstract.db")
    legacy.execute(
        "CREATE TABLE videos (id TEXT PRIMARY KEY, filename TEXT NOT NULL, content_type TEXT,"
        " duration REAL, width INTEGER, height INTEGER, path TEXT NOT NULL,"
        " created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))"
    )
    legacy.execute("INSERT INTO videos (id, filename, path) VALUES ('old', 'a.mp4', '/x/a.mp4')")
    legacy.commit()
    legacy.close()

    with session() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        row = conn.execute("SELECT proxy_job_id FROM videos WHERE id = 'old'").fetchone()
    proxy_job_id = row[0]

    assert version == SCHEMA_VERSION
    job = jobs.get_job(proxy_job_id)
    assert job is not None and job.kind == "proxy" and job.status == "queued"
