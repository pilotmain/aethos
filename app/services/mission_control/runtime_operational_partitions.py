# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime operational partitions — selective hydration (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any

PARTITIONS = ("live", "operational", "governance", "intelligence", "archive")


def build_runtime_operational_partitions(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = (truth.get("operational_pressure") or {}).get("level", "low")
    return {
        "live": {
            "office": bool(truth.get("office")),
            "runtime_health": truth.get("runtime_health"),
            "active": True,
        },
        "operational": {
            "continuity": bool(truth.get("operational_continuity_engine")),
            "recovery": bool(truth.get("operational_recovery_state")),
            "pressure": pressure,
        },
        "governance": {
            "timeline": bool(truth.get("unified_operational_timeline")),
            "experience": bool(truth.get("governance_experience")),
        },
        "intelligence": {
            "routing": bool(truth.get("intelligent_routing")),
            "advisories": len(truth.get("strategic_recommendations") or []),
        },
        "archive": {
            "worker_archive": truth.get("worker_memory_archive"),
            "long_horizon": bool(truth.get("runtime_long_horizon")),
        },
        "partition_throttling": pressure == "high",
        "selective_hydration": True,
    }


def partition_keys(partition: str) -> frozenset[str]:
    mapping = {
        "live": frozenset({"office", "runtime_health", "runtime_agents", "routing_summary"}),
        "operational": frozenset({"operational_continuity_engine", "operational_recovery_state"}),
        "governance": frozenset({"unified_operational_timeline", "governance_experience"}),
        "intelligence": frozenset({"intelligent_routing", "strategic_recommendations"}),
        "archive": frozenset({"worker_memory_archive", "runtime_long_horizon"}),
    }
    return mapping.get(partition, frozenset())
