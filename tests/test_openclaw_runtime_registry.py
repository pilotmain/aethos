# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime registry snapshot reads ``aethos.json``."""

from __future__ import annotations

from app.runtime.runtime_registry import get_runtime_snapshot


def test_runtime_snapshot_has_runtime_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    snap = get_runtime_snapshot()
    assert isinstance(snap.get("runtime_id"), str) and len(snap["runtime_id"]) > 4
