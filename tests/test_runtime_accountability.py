# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operational_trust import build_runtime_accountability
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_accountability_orchestrator_owned() -> None:
    acc = build_runtime_accountability({})
    assert acc.get("orchestrator_owned") is True
    truth = build_runtime_truth(user_id=None)
    assert (truth.get("runtime_accountability") or {}).get("no_hidden_execution") is True
