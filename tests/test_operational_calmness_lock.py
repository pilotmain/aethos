# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_calmness_metrics import (
    build_runtime_calmness_metrics,
    build_runtime_signal_health,
)
from app.services.mission_control.operational_calmness_lock import build_calmness_lock


def test_operational_calmness_lock_noise_reduction() -> None:
    lock = build_calmness_lock({"unified_operational_timeline": {"deduped_from": 10, "entry_count": 4}})
    assert lock["operational_noise_reduction"] >= 0.5


def test_enterprise_calmness_metrics_launch() -> None:
    m = build_runtime_calmness_metrics({})
    assert "calmness_score" in m
    assert m["noise_reduction_ratio"] is not None
    h = build_runtime_signal_health({})
    assert "event_signal_quality" in h
