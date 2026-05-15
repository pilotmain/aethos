# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Session rows in ``aethos.json`` survive reload."""

from __future__ import annotations

from app.runtime.runtime_sessions import append_session_record
from app.runtime.runtime_state import load_runtime_state


def test_session_record_survives_reload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    append_session_record("sess_p1", meta={"channel": "web"})
    rows = load_runtime_state().get("sessions") or []
    assert any(r.get("id") == "sess_p1" for r in rows)
