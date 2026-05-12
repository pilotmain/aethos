# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Truth states for operator orchestration (Mission Control wiring is incremental)."""

from __future__ import annotations

from app.services.operator_runners.base import TruthState


def test_truth_state_enum_values() -> None:
    assert TruthState.verified.value == "verified"
    assert TruthState.diagnostic_only.value == "diagnostic_only"
    assert TruthState.access_required.value == "access_required"
