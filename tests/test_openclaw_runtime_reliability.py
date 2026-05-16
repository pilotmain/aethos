# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime import runtime_reliability
from app.runtime.events import runtime_metrics as rm
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_summarize_reliability_healthy_empty_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    rel = runtime_reliability.summarize_runtime_reliability(st)
    assert rel.get("severity") == "healthy"
    assert rel.get("integrity_ok") is True


def test_boot_bumps_restart_cycle_in_stability(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    rm.bump_runtime_boot(st)
    rs = st.get("runtime_stability") or {}
    assert int(rs.get("restart_cycles") or 0) >= 1
    save_runtime_state(st)
    st2 = load_runtime_state()
    rs2 = st2.get("runtime_stability") or {}
    assert int(rs2.get("restart_cycles") or 0) >= 1
