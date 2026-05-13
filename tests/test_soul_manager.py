# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import soul_manager as sm


def test_snapshot_and_history_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEXA_SOUL_HISTORY_LIMIT", "10")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        uid = "web_test_u1"
        p1 = sm.snapshot_user_soul_before_write(uid, "# Soul\n\nv1\n")
        assert p1 and Path(p1).is_file()
        sm.snapshot_user_soul_before_write(uid, "# Soul\n\nv2\n")
        hist = sm.get_user_soul_history(uid)
        assert len(hist) == 2
        assert sm.read_user_soul_version(uid, hist[0]) is not None
    finally:
        get_settings.cache_clear()


def test_match_soul_versioning_intent() -> None:
    from app.services.host_executor_intent import match_soul_versioning_intent

    k, m = match_soul_versioning_intent("show soul history")
    assert k == "soul_history"
    k2, m2 = match_soul_versioning_intent("rollback soul to 2026-05-13_10-30-15_000001")
    assert k2 == "soul_rollback" and m2 and m2.group(1) == "2026-05-13_10-30-15_000001"
    k3, _ = match_soul_versioning_intent("undo soul change")
    assert k3 == "soul_undo"
