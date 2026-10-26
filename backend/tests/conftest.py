"""Isolate MEDIA_ROOT per test so uploads never touch the repo."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_media_root(tmp_path, monkeypatch):
    root = tmp_path / "media"
    monkeypatch.setenv("MEDIA_ROOT", str(root))
    return root
