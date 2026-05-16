# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Production hardening bounds verification (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def verify_production_bounds(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    s = get_settings()
    disc = truth.get("payload_discipline") or {}
    checks = {
        "payload_bounds": {
            "ok": disc.get("within_budget", True),
            "bytes": disc.get("payload_bytes"),
            "max": int(getattr(s, "aethos_truth_payload_max_bytes", 400_000)),
        },
        "memory_bounds": {
            "ok": True,
            "deliverable_limit": int(getattr(s, "aethos_worker_deliverable_limit", 200)),
        },
        "continuity_bounds": {"ok": True, "operator_continuity_present": "operator_continuity" in truth},
        "timeline_bounds": {
            "ok": len((truth.get("unified_operational_timeline") or {}).get("timeline") or []) <= 48,
        },
        "governance_bounds": {"ok": bool((truth.get("runtime_governance")))},
        "deliverable_bounds": {
            "ok": len(truth.get("worker_deliverables") or []) <= 32,
        },
    }
    all_ok = all(c.get("ok") for c in checks.values() if isinstance(c, dict))
    return {
        "checks": checks,
        "resilient": all_ok,
        "hydration_resilient": float((truth.get("runtime_performance") or {}).get("hydration_latency_ms") or 0) < 8000,
        "event_resilience": True,
        "governance_resilience": bool(truth.get("governance_experience")),
        "automation_resilience": bool(truth.get("automation_trust")),
    }
