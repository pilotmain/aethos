# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime truth integrity validation (Phase 4 Step 6)."""

from __future__ import annotations

import json
from typing import Any

_MAX_BRANCH_BYTES = 48_000
_CRITICAL_KEYS = frozenset(
    {
        "office",
        "runtime_agents",
        "routing_summary",
        "intelligent_routing",
        "operational_recovery_state",
        "runtime_awareness",
    }
)


def _branch_bytes(value: Any) -> int:
    try:
        return len(json.dumps(value, default=str))
    except Exception:
        return 0


def validate_truth_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    oversized: list[str] = []
    fragmented: list[str] = []
    stale: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []

    for key, value in truth.items():
        if key in seen:
            duplicates.append(key)
        seen.add(key)
        nbytes = _branch_bytes(value)
        if nbytes > _MAX_BRANCH_BYTES:
            oversized.append(key)
        if key.startswith("_"):
            fragmented.append(key)

    hm = truth.get("hydration_metrics") or {}
    if isinstance(hm, dict) and hm.get("stale"):
        stale.append("hydration_metrics")
    if truth.get("runtime_resilience", {}).get("status") == "stale":
        stale.append("runtime_resilience")

    issues = len(duplicates) + len(oversized) + len(stale)
    score = max(0.0, min(1.0, 1.0 - issues * 0.08))

    return {
        "truth_integrity_score": round(score, 3),
        "fragmented_sections": fragmented[:12],
        "oversized_sections": oversized[:12],
        "stale_sections": stale[:12],
        "duplicate_keys": duplicates[:12],
        "critical_keys_present": {k: k in truth for k in _CRITICAL_KEYS},
        "cohesive": score >= 0.85 and not duplicates,
    }
