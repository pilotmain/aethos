# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Privacy-aware operational posture for Mission Control (Phase 3 Step 2)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.privacy.llm_privacy_gate import recent_llm_privacy_decisions
from app.privacy.privacy_policy import current_privacy_mode
from app.privacy.privacy_snapshot import build_mission_control_privacy_panel
from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display, list_normalized_events


def build_privacy_operational_posture() -> dict[str, Any]:
    s = get_settings()
    mode = current_privacy_mode(s)
    panel = build_mission_control_privacy_panel()
    events = aggregate_events_for_display(limit=24, category="privacy")
    raw = list_normalized_events(limit=80, category="privacy")
    st = load_runtime_state()
    blocked = sum(1 for e in raw if "block" in str(e.get("event_type") or ""))
    redactions = sum(int((e.get("payload") or {}).get("redactions") or 0) for e in raw if isinstance(e.get("payload"), dict))
    llm_routing = recent_llm_privacy_decisions(limit=12)
    egress_allowed = sum(1 for r in llm_routing if r.get("egress_allowed") is True)
    egress_blocked = sum(1 for r in llm_routing if r.get("egress_allowed") is False)
    artifacts = st.get("sensitive_artifacts") or []
    if not isinstance(artifacts, list):
        artifacts = []

    return {
        "privacy_posture": {
            "mode": mode.value,
            "local_first": panel.get("local_first_enabled"),
            "local_only": mode.value == "local_only",
            "pii_redaction_enabled": panel.get("pii_redaction_enabled"),
            "egress_guard_enabled": panel.get("external_egress_guard_enabled"),
        },
        "pii_detections": len([e for e in raw if "pii" in str(e.get("event_type") or "").lower()]),
        "egress_decisions": {
            "allowed": egress_allowed,
            "blocked": egress_blocked,
            "recent": llm_routing[:8],
        },
        "local_cloud_routing": {
            "local_first": panel.get("local_first_enabled"),
            "require_local_model": panel.get("require_local_model"),
            "allow_external_fallback": panel.get("allow_external_fallback"),
        },
        "sensitive_artifacts": artifacts[-12:] if isinstance(artifacts, list) else [],
        "redaction_counts": redactions,
        "blocked_operations": blocked,
        "privacy_events": events[:16],
        "workflow_posture": _workflow_posture(st),
        "audit_enabled": panel.get("privacy_audit_enabled"),
    }


def _workflow_posture(st: dict[str, Any]) -> list[dict[str, Any]]:
    repairs = st.get("repair_contexts") or {}
    latest = repairs.get("latest_by_project") if isinstance(repairs, dict) else {}
    rows: list[dict[str, Any]] = []
    if isinstance(latest, dict):
        for pid, rid in list(latest.items())[:8]:
            bucket = repairs.get(pid) if isinstance(repairs.get(pid), dict) else {}
            row = bucket.get(rid) if isinstance(bucket, dict) and isinstance(rid, str) else None
            if not isinstance(row, dict):
                continue
            bd = row.get("brain_decision") or {}
            rows.append(
                {
                    "workflow": f"repair:{pid}",
                    "privacy_mode": bd.get("privacy_mode"),
                    "provider": bd.get("selected_provider"),
                    "privacy_safe_plan": bool(row.get("plan_validated")),
                }
            )
    return rows
