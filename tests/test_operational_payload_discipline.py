# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operational_payload_discipline import (
    build_payload_discipline_block,
    summarize_truth_payload,
)
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_payload_discipline_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert "payload_discipline" in truth
    block = build_payload_discipline_block(truth)
    assert "payload_bytes" in block
    assert block.get("payload_max_bytes", 0) > 0


def test_summarize_caps_events() -> None:
    raw = {"runtime_events": [{"id": i} for i in range(100)]}
    out = summarize_truth_payload(raw)
    assert len(out.get("runtime_events") or []) <= 32
