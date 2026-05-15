# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.events.runtime_metrics import bump_scheduler_tick
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_runtime_metrics_scheduler_tick(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    bump_scheduler_tick(st, ticks=42)
    save_runtime_state(st)
    st2 = load_runtime_state()
    assert int((st2.get("runtime_metrics") or {}).get("scheduler_ticks") or 0) == 42
