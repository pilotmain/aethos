# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_startup_experience import build_runtime_startup_experience


def test_runtime_warmup_flow_partial_mode() -> None:
    out = build_runtime_startup_experience({"hydration_progress": {"partial": True, "percent_estimate": 0.4}})
    exp = out["runtime_startup_experience"]
    assert exp["partial_mode"] is True
    assert exp["readiness_percent"] <= 0.5
    warmup = out["runtime_warmup_awareness"]
    assert warmup["partial_mode"] is True
