# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Progressive / tiered runtime hydration (Phase 4 Step 7)."""

from __future__ import annotations

import time
from typing import Any

from app.services.mission_control.runtime_priority_scheduler import (
    TIERS,
    build_hydration_queue,
    slices_up_to_tier,
)
from app.services.mission_control.runtime_slice_persistence import load_persisted_slices


def hydrate_progressive_truth(
    *,
    user_id: str | None = None,
    max_tier: str = "advisory",
) -> dict[str, Any]:
    """Build truth incrementally by priority tier; merge persisted warm slices first."""
    from app.services.mission_control.runtime_hydration import (
        _build_core_slice,
        _build_derived_slice,
        _build_governance_slice,
        _build_intelligence_slice,
        _build_worker_memory_slice,
        _build_workers_slice,
        _build_workspace_slice,
        get_cached_slice,
    )

    allowed = slices_up_to_tier(max_tier)
    truth: dict[str, Any] = dict(load_persisted_slices(user_id))
    truth["hydration_progress"] = {"tier": "warm", "partial": True}
    tier_times: dict[str, float] = {}

    if "core" in allowed:
        t0 = time.monotonic()
        core = get_cached_slice("core", user_id, lambda: _build_core_slice(user_id))
        truth.update({k: v for k, v in core.items() if not k.startswith("_")})
        tier_times["critical"] = round((time.monotonic() - t0) * 1000.0, 2)

    if "workers" in allowed:
        core = truth
        workers = get_cached_slice("workers", user_id, lambda: _build_workers_slice(user_id, core))
        truth.update({k: v for k, v in workers.items() if not k.startswith("_")})

    if "governance" in allowed:
        t0 = time.monotonic()
        gov = get_cached_slice("governance", user_id, _build_governance_slice)
        truth.update({k: v for k, v in gov.items() if not k.startswith("_")})
        tier_times["operational"] = round((time.monotonic() - t0) * 1000.0, 2)

    for name, builder in (
        ("workspace", _build_workspace_slice),
        ("worker_memory", _build_worker_memory_slice),
    ):
        if name in allowed:
            part = get_cached_slice(name, user_id, builder)
            truth.update({k: v for k, v in part.items() if not k.startswith("_")})

    if "intelligence" in allowed:
        t0 = time.monotonic()
        core = truth
        intel = get_cached_slice("intelligence", user_id, lambda: _build_intelligence_slice(user_id, core))
        truth.update({k: v for k, v in intel.items() if not k.startswith("_")})
        tier_times["advisory"] = round((time.monotonic() - t0) * 1000.0, 2)

    if "derived" in allowed:
        derived = get_cached_slice("derived", user_id, lambda: _build_derived_slice(user_id, truth))
        truth.update(derived)

    truth["hydration_progress"] = {
        "max_tier": max_tier,
        "tiers_complete": [t for t in TIERS if t in tier_times or t == "critical"],
        "tier_build_ms": tier_times,
        "partial": max_tier != "background",
    }
    truth["hydration_queue"] = build_hydration_queue(truth)
    return truth


def build_hydration_status(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "queue": build_hydration_queue(truth),
        "progress": truth.get("hydration_progress") or {},
        "metrics": truth.get("hydration_metrics") or {},
        "async_mode": "progressive_tiers",
    }
