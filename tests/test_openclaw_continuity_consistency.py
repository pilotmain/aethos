# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic ``summarize_runtime_continuity`` under repeated reads (confidence lock)."""

from __future__ import annotations

import copy

from app.runtime import runtime_continuity
from app.runtime.events import runtime_metrics as rm
from app.runtime.runtime_state import load_runtime_state


def test_continuity_summary_stable_across_repeated_reads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    rm.bump_runtime_boot(st)
    runtime_continuity.bump_continuity_repairs(st, 2)
    baseline = copy.deepcopy(st)
    first = runtime_continuity.summarize_runtime_continuity(baseline)
    for rate_key in (
        "restart_recovery_success_rate",
        "deployment_recovery_success_rate",
        "rollback_recovery_success_rate",
    ):
        r = float(first[rate_key])
        assert 0.0 <= r <= 1.0
    for _ in range(100):
        snap = runtime_continuity.summarize_runtime_continuity(copy.deepcopy(baseline))
        assert snap == first
