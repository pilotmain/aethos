# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.runtime import runtime_reliability
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles


@pytest.mark.production_like
def test_large_warning_pressure_churn_stays_integrity_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = repeated_cycles(large=160)
    st = load_runtime_state()
    m = st.setdefault("runtime_metrics", {})
    assert isinstance(m, dict)
    for i in range(n):
        runtime_reliability.bump_retry_pressure(st, 1)
        runtime_reliability.bump_queue_pressure_stability(st, 1)
        runtime_reliability.bump_runtime_degradation(st, 1)
        m["adaptive_retry_blocked_total"] = min(12, (i // 3) % 13)
        m["deployment_failed_total"] = min(4, (i // 5) % 5)
        rel = runtime_reliability.summarize_runtime_reliability(st)
        assert rel.get("severity") != "critical"
        inv = validate_runtime_state(st)
        assert inv.get("ok") is True
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
