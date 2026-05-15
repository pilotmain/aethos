# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.paths import get_runtime_corruption_quarantine_dir, get_runtime_state_path
from app.runtime.runtime_state import load_runtime_state


def test_invalid_json_file_quarantined_and_runtime_recovers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    p = get_runtime_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json<<", encoding="utf-8")
    st = load_runtime_state()
    assert isinstance(st.get("runtime_id"), str) and len(str(st.get("runtime_id"))) > 4
    qdir = get_runtime_corruption_quarantine_dir()
    assert qdir.is_dir()
    assert any(qdir.glob("aethos.corrupt*.json"))
