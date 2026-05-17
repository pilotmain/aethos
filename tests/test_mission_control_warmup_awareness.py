# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_startup_experience import build_runtime_startup_experience
from app.services.runtime.runtime_launch_orchestration import build_warmup_awareness_payload


def test_mission_control_warmup_awareness_payload() -> None:
    out = build_runtime_startup_experience({"hydration_progress": {"partial": True}})
    exp = out["runtime_startup_experience"]
    assert exp.get("operator_readiness_state")
    assert exp.get("office_home_intro")
    warmup = out.get("runtime_warmup_awareness") or {}
    assert warmup.get("checklist")
    assert warmup.get("partial_mode") is True


def test_warmup_checklist_marks_api_complete_when_reachable() -> None:
    blob = build_warmup_awareness_payload(api_reachable=True, mc_reachable=False, hydration_partial=True)
    checklist = blob["runtime_warmup_awareness"]["checklist"]
    api = next(c for c in checklist if c["id"] == "api")
    assert api["complete"] is True
