# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_metrics_discipline import approx_payload_bytes, get_runtime_discipline_metrics
from app.services.mission_control.runtime_truth import build_runtime_truth
from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth


def test_truth_build_records_discipline_metrics() -> None:
    get_cached_runtime_truth(None, lambda uid: build_runtime_truth(user_id=uid))
    m = get_runtime_discipline_metrics()
    assert "last_payload_approx_bytes" in m or "payload_samples" in m


def test_truth_payload_has_reasonable_key_count() -> None:
    truth = build_runtime_truth(user_id=None)
    assert len(truth) >= 20
    assert approx_payload_bytes(truth) < 2_000_000
