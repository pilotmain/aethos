# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic ``summarize_runtime_reliability`` under repeated reads (confidence lock)."""

from __future__ import annotations

import copy

from app.runtime import runtime_reliability
from app.runtime.events import runtime_metrics as rm
from app.runtime.runtime_state import load_runtime_state


def test_reliability_summary_stable_across_repeated_reads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    rm.bump_runtime_boot(st)
    runtime_reliability.bump_retry_pressure(st, 3)
    runtime_reliability.bump_queue_pressure_stability(st, 2)
    baseline = copy.deepcopy(st)
    first = runtime_reliability.summarize_runtime_reliability(baseline)
    for _ in range(48):
        snap = runtime_reliability.summarize_runtime_reliability(copy.deepcopy(baseline))
        assert snap == first
        assert snap["severity"] in ("healthy", "warning", "degraded", "critical")
        assert isinstance(snap.get("reasons"), list)
