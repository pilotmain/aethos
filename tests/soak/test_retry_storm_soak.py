# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.runtime import runtime_reliability
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.soak
def test_stability_counters_bounded_under_synthetic_pressure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    k = 300 if os.environ.get("AETHOS_SOAK_LONG") == "1" else 80
    for _ in range(k):
        runtime_reliability.bump_retry_pressure(st, 1)
        runtime_reliability.bump_queue_pressure_stability(st, 1)
    rs = st.get("runtime_stability") or {}
    assert int(rs.get("retry_pressure_events") or 0) == k
    assert int(rs.get("queue_pressure_events") or 0) == k
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
