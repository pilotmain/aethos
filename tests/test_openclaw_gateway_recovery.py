# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Stale gateway PID recovery — persistent runtime parity."""

from __future__ import annotations

from app.runtime.runtime_recovery import reconcile_stale_gateway_pid
from app.runtime.runtime_state import default_runtime_state, load_runtime_state, save_runtime_state


def test_reconcile_clears_dead_pid(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = default_runtime_state()
    st["gateway"]["running"] = True
    st["gateway"]["pid"] = 99999
    save_runtime_state(st)
    st2 = load_runtime_state()
    st3 = reconcile_stale_gateway_pid(st2)
    save_runtime_state(st3)
    gw = load_runtime_state()["gateway"]
    assert gw.get("running") is False
    assert gw.get("pid") in (None, 0)
