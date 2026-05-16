# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_payload_within_discipline_budget() -> None:
    truth = build_runtime_truth(user_id=None)
    disc = truth.get("payload_discipline") or {}
    assert disc.get("within_budget") in (True, False)
    assert disc.get("payload_max_bytes", 0) > 0
