# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_supervisor import ensure_supervisor, restart_supervisor
from app.runtime.runtime_state import load_runtime_state


def test_supervisor_restart_increments(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    sup = ensure_supervisor(st, loop_type="retry_supervisor", user_id="u1")
    sid = str(sup["supervisor_id"])
    r1 = restart_supervisor(st, sid)
    r2 = restart_supervisor(st, sid)
    assert r1 and r2 and int(r2.get("restarts") or 0) == 2
