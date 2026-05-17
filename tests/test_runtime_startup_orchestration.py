# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.runtime.runtime_launch_orchestration import UNIFIED_LAUNCH_STAGES, launch_stage_count
from app.services.runtime.runtime_progressive_startup import PROGRESSIVE_STARTUP_STAGES
from app.services.runtime.runtime_startup_orchestration import build_runtime_startup_orchestration


def test_unified_launch_stages_are_eight() -> None:
    assert launch_stage_count() == 8
    assert len(UNIFIED_LAUNCH_STAGES) == 8
    assert PROGRESSIVE_STARTUP_STAGES == UNIFIED_LAUNCH_STAGES


def test_orchestration_metadata_matches_stage_count() -> None:
    blob = build_runtime_startup_orchestration({})
    assert blob["runtime_startup_orchestration"]["progressive_stages"] == 8
