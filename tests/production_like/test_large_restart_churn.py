# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.runtime import runtime_continuity
from app.runtime.events import runtime_metrics as rm
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_large_restart_churn_with_persisted_boots(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = 95 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 42
    st = load_runtime_state()
    for i in range(n):
        rm.bump_runtime_boot(st)
        if i % 11 == 0:
            cont = runtime_continuity.summarize_runtime_continuity(st)
            r = float(cont["restart_recovery_success_rate"])
            assert 0.0 <= r <= 1.0
            save_runtime_state(st)
            st = load_runtime_state()
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
