"""SQLite connection and schema migrations.

The API and the worker share one database file under MEDIA_ROOT. WAL mode lets the
API read while the worker writes progress. Migrations are numbered by
`PRAGMA user_version` and run once, inside an IMMEDIATE transaction, so two
processes starting together do not both apply them.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_MIGRATIONS: list[tuple[str, ...]] = [
    # 1: M1 videos table.
    (
        """
        CREATE TABLE IF NOT EXISTS videos (
          id TEXT PRIMARY KEY,
          filename TEXT NOT NULL,
          content_type TEXT,
          duration REAL,
          width INTEGER,
          height INTEGER,
          path TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """,
    ),
    # 2: probe details and proxies, projects with ordered clips, the job queue.
    (
        "ALTER TABLE videos ADD COLUMN fps REAL",
        "ALTER TABLE videos ADD COLUMN rotation INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE videos ADD COLUMN video_codec TEXT",
        "ALTER TABLE videos ADD COLUMN has_audio INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE videos ADD COLUMN variable_fps INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE videos ADD COLUMN proxy_path TEXT",
        "ALTER TABLE videos ADD COLUMN proxy_job_id TEXT",
        """
        CREATE TABLE projects (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
          updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """,
        """
        CREATE TABLE clips (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          video_id TEXT NOT NULL REFERENCES videos(id),
          position INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """,
        "CREATE INDEX clips_project ON clips(project_id, position)",
        """
        CREATE TABLE jobs (
          id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          ref_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued',
          stage TEXT,
          progress REAL NOT NULL DEFAULT 0,
          message TEXT,
          error TEXT,
          cancel_requested INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
          started_at TEXT,
          finished_at TEXT
        )
        """,
        "CREATE INDEX jobs_status ON jobs(status, created_at)",
        # Videos uploaded during M1 have no proxy yet. Queue one for each.
        """
        INSERT INTO jobs (id, kind, ref_id)
        SELECT lower(hex(randomblob(16))), 'proxy', id FROM videos
        """,
        """
        UPDATE videos SET proxy_job_id = (
          SELECT jobs.id FROM jobs WHERE jobs.kind = 'proxy' AND jobs.ref_id = videos.id
        )
        """,
    ),
    # 3: the object each clip follows, as JSON (frame, box in source pixels, how chosen).
    ("ALTER TABLE clips ADD COLUMN target TEXT",),
    # 4: the analysis of that target: its job, and the signals file once done.
    (
        "ALTER TABLE clips ADD COLUMN analysis_job_id TEXT",
        "ALTER TABLE clips ADD COLUMN analysis_path TEXT",
    ),
    # 5: how to cut the clip (sensitivity, manual edits) and the parts it gives, as JSON.
    (
        "ALTER TABLE clips ADD COLUMN segment_params TEXT",
        "ALTER TABLE clips ADD COLUMN segment_edits TEXT",
        "ALTER TABLE clips ADD COLUMN cuts TEXT",
    ),
    # 6: transitions and title cards for the whole sequence, and finished renders.
    (
        "ALTER TABLE projects ADD COLUMN sequence TEXT",
        """
        CREATE TABLE renders (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          job_id TEXT NOT NULL,
          settings TEXT NOT NULL,
          path TEXT,
          filename TEXT NOT NULL,
          duration REAL,
          size_bytes INTEGER,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """,
        "CREATE INDEX renders_project ON renders(project_id, created_at)",
    ),
    # 7: the project's shared target: which clip it was picked in, its class, its look.
    ("ALTER TABLE projects ADD COLUMN reference TEXT",),
]

SCHEMA_VERSION = len(_MIGRATIONS)


def media_root() -> Path:
    return Path(os.environ.get("MEDIA_ROOT", "data"))


def _migrate(conn: sqlite3.Connection) -> None:
    if conn.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for statements in _MIGRATIONS[version:]:
            for statement in statements:
                conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def connect() -> sqlite3.Connection:
    root = media_root()
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "oxstract.db", timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    return conn


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    """A connection in autocommit mode, closed on exit."""

    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """A connection inside BEGIN IMMEDIATE, committed on success."""

    with session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
