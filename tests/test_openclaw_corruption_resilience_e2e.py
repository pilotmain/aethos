# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""End-to-end corruption handling (invalid JSON → quarantine + fresh state)."""

from __future__ import annotations

from app.core.paths import get_runtime_corruption_quarantine_dir, get_runtime_state_path
from app.runtime.runtime_state import load_runtime_state


def test_corrupt_file_quarantined_e2e(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    p = get_runtime_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[[[", encoding="utf-8")
    load_runtime_state()
    assert any(get_runtime_corruption_quarantine_dir().glob("aethos.corrupt*.json"))
