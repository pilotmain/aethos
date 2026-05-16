# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_metrics_discipline import approx_payload_bytes, get_runtime_discipline_metrics
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_payload_bounded_and_tracked() -> None:
    truth = build_runtime_truth(user_id=None)
    nbytes = approx_payload_bytes(truth)
    assert nbytes < 2_000_000
    m = get_runtime_discipline_metrics()
    assert "event_buffer_size" in m
