# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_identity import CANONICAL_LABELS, build_runtime_identity
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_identity_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    ident = truth.get("runtime_identity") or {}
    assert ident.get("orchestrator_central") is True
    assert ident.get("single_truth_path") is True


def test_canonical_labels() -> None:
    assert CANONICAL_LABELS["orchestrator"] == "AethOS Orchestrator"
