"""Video storage: files on disk, metadata in SQLite (M1)."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  content_type TEXT,
  duration REAL,
  width INTEGER,
  height INTEGER,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


@dataclass(frozen=True)
class VideoRecord:
    id: str
    filename: str
    content_type: str | None
    duration: float | None
    width: int | None
    height: int | None
    path: str


def media_root() -> Path:
    return Path(os.environ.get("MEDIA_ROOT", "data"))


def _connect() -> sqlite3.Connection:
    root = media_root()
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "oxstract.db")
    conn.execute(_SCHEMA)
    return conn


def save_video(record: VideoRecord) -> VideoRecord:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO videos (id, filename, content_type, duration, width, height, path)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.filename,
                record.content_type,
                record.duration,
                record.width,
                record.height,
                record.path,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def get_video(video_id: str) -> VideoRecord | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, filename, content_type, duration, width, height, path"
            " FROM videos WHERE id = ?",
            (video_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return VideoRecord(*row)
