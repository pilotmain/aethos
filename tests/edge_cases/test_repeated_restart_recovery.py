# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.runtime.events import runtime_metrics as rm
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.edge_cases
def test_repeated_boot_continuity_counters(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    for _ in range(30):
        rm.bump_runtime_boot(st)
    save_runtime_state(st)
    st2 = load_runtime_state()
    rc = st2.get("runtime_continuity") or {}
    assert int(rc.get("restart_recovery_attempts") or 0) >= 30
    assert validate_runtime_state(st2).get("ok") is True
