# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_save_runtime_state_twice_succeeds(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    st["runtime_resilience"] = {"probe": 1}
    save_runtime_state(st)
    st2 = load_runtime_state()
    st2["runtime_resilience"] = {"probe": 2}
    save_runtime_state(st2)
    st3 = load_runtime_state()
    assert (st3.get("runtime_resilience") or {}).get("probe") == 2
