# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational explainability — concise runtime-derived reasons (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any


def build_operational_explainability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    routing = truth.get("routing_summary") or {}
    explanations: list[dict[str, Any]] = []

    if routing.get("fallback_used"):
        explanations.append(
            {
                "topic": "provider_fallback",
                "reason": routing.get("reason") or "Primary provider unavailable; fallback routing applied.",
                "source": "brain_router",
            }
        )

    for rec in ((truth.get("runtime_recommendations") or {}).get("recommendations") or [])[:4]:
        if isinstance(rec, dict):
            explanations.append(
                {
                    "topic": "recommendation",
                    "reason": rec.get("reason") or rec.get("message"),
                    "kind": rec.get("kind"),
                    "requires_approval": rec.get("requires_approval", True),
                }
            )

    office = truth.get("office") or {}
    pressure = office.get("pressure") if isinstance(office, dict) else {}
    if isinstance(pressure, dict) and any(pressure.get(k) for k in ("queue", "retry", "deployment")):
        explanations.append(
            {
                "topic": "runtime_escalation",
                "reason": "Operational pressure detected in office view (queue/retry/deployment).",
                "source": "office",
            }
        )

    cont = truth.get("operator_continuity") or {}
    if isinstance(cont, dict) and cont.get("resume_available"):
        explanations.append(
            {
                "topic": "continuity_resume",
                "reason": "Prior operator session can resume from continuity snapshot.",
                "source": "operator_continuity",
            }
        )

    return {
        "explanations": explanations[:12],
        "worker_selection": _explain_worker_selection(truth),
        "concise": True,
        "enterprise_readable": True,
    }


def _explain_worker_selection(truth: dict[str, Any]) -> str:
    rw = truth.get("runtime_workers") or {}
    active = rw.get("active_count") if isinstance(rw, dict) else 0
    return f"Workers selected by orchestrator assignment; {active} active runtime agents."
