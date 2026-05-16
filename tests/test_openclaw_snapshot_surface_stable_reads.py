# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control snapshot ``resilience`` slice identical across repeated reads after a persisted bump."""

from __future__ import annotations

import copy

from app.runtime.events import runtime_metrics as rm
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot

from tests.parity_freeze_gate import MIN_REPEATED_CYCLES


def test_snapshot_resilience_stable_after_persisted_boot(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    rm.bump_runtime_boot(st)
    save_runtime_state(st)
    first: dict | None = None
    for _ in range(MIN_REPEATED_CYCLES):
        snap = build_orchestration_runtime_snapshot("u_snap")
        res = snap.get("resilience") or {}
        if first is None:
            first = copy.deepcopy(res)
        else:
            assert res == first
