# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 14 — Mission Control state sizing guardrails (aligned with UI caps)."""

from __future__ import annotations

from app.services.mission_control.nexa_next_state import (
    MC_MAX_ARTIFACTS_PER_MISSION,
    MC_MAX_MISSIONS_LOADED,
)


def test_execution_snapshot_limits_constants() -> None:
    assert MC_MAX_MISSIONS_LOADED == 50
    assert MC_MAX_ARTIFACTS_PER_MISSION == 100
