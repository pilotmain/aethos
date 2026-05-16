# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.intelligent_runtime_evolution import build_intelligent_runtime_evolution


def test_intelligent_runtime_evolution() -> None:
    out = build_intelligent_runtime_evolution({})
    assert out.get("orchestrator_owned") is True
