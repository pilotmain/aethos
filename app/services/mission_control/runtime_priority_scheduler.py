# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Priority-tier scheduling for runtime hydration (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any

TIERS = ("critical", "operational", "advisory", "background")

SLICE_TIER: dict[str, str] = {
    "core": "critical",
    "workers": "critical",
    "governance": "operational",
    "workspace": "operational",
    "worker_memory": "operational",
    "intelligence": "advisory",
    "derived": "advisory",
}

TIER_ORDER: dict[str, int] = {name: i for i, name in enumerate(TIERS)}


def tier_for_slice(slice_name: str) -> str:
    return SLICE_TIER.get(slice_name, "background")


def slices_up_to_tier(max_tier: str) -> frozenset[str]:
    limit = TIER_ORDER.get(max_tier, len(TIERS) - 1)
    return frozenset(s for s, t in SLICE_TIER.items() if TIER_ORDER.get(t, 99) <= limit)


def build_hydration_queue(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hm = truth.get("hydration_metrics") or {}
    pending = []
    for tier in TIERS:
        pending.append({"tier": tier, "slices": [s for s, t in SLICE_TIER.items() if t == tier]})
    return {
        "tiers": list(TIERS),
        "queue": pending,
        "generation_id": hm.get("hydration_generation_id"),
        "deferred_operations": truth.get("runtime_operational_throttling", {}).get("deferred_operations") or [],
    }
