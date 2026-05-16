# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.orchestration import runtime_dispatcher
from app.runtime.events import runtime_metrics as rm
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import MIN_REPEATED_CYCLES, repeated_cycles


@pytest.mark.production_like
def test_restart_style_boot_and_dispatch_maintains_integrity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    outer = repeated_cycles(large=45)
    st = load_runtime_state()
    for _ in range(outer):
        rm.bump_runtime_boot(st)
        for _ in range(3):
            runtime_dispatcher.dispatch_once(st)
    save_runtime_state(st)
    inv = validate_runtime_state(load_runtime_state())
    assert inv.get("ok") is True
    rs = load_runtime_state().get("runtime_stability") or {}
    assert int(rs.get("restart_cycles") or 0) >= MIN_REPEATED_CYCLES
