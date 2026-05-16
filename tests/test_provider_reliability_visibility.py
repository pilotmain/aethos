# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_confidence import build_provider_reliability
from app.services.mission_control.runtime_truth import build_runtime_truth
from app.runtime.runtime_state import load_runtime_state


def test_provider_reliability_summary() -> None:
    truth = build_runtime_truth(user_id=None)
    rel = build_provider_reliability(truth, load_runtime_state())
    assert "summary" in rel
    assert "providers" in rel
