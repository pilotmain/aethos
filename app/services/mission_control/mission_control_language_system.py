# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control language system — enterprise-friendly terminology (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

USER_FACING_TERMS: dict[str, str] = {
    "runtime_pressure": "Operational load",
    "degraded": "Needs attention",
    "escalation": "Critical operational issue",
    "throttling": "Performance protection",
    "continuity": "Operational continuity",
    "critical": "Critical",
    "warning": "Attention recommended",
    "healthy": "Operating normally",
    "recovering": "Recovering",
    "failed": "Interrupted",
    "offline": "Unavailable",
    "queue_pressure": "Task queue load",
    "retry_pressure": "Retry activity",
    "deployment_pressure": "Deployment activity",
}


def translate_term(key: str, *, fallback: str | None = None) -> str:
    k = (key or "").strip().lower().replace(" ", "_")
    return USER_FACING_TERMS.get(k) or fallback or key.replace("_", " ").title()


def apply_user_facing_language(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return payload with common status fields translated for MC surfaces."""
    payload = dict(payload or {})
    for field in ("status", "health", "level", "overall", "pressure_level"):
        val = payload.get(field)
        if isinstance(val, str):
            payload[f"{field}_label"] = translate_term(val, fallback=val)
    pressure = payload.get("pressure")
    if isinstance(pressure, dict):
        p2 = dict(pressure)
        for k, v in list(p2.items()):
            if v is True or v == "true":
                p2[f"{k}_label"] = translate_term(k)
        payload["pressure"] = p2
    return payload


def build_mission_control_language_system() -> dict[str, Any]:
    return {
        "canonical_terms": dict(USER_FACING_TERMS),
        "tone": "enterprise_calm",
        "consistent": True,
        "bounded": True,
    }
