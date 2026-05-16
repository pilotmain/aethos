# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational identity lock (Phase 4 Step 10)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_identity import CANONICAL_LABELS, build_runtime_identity


OPERATIONAL_TERMINOLOGY: dict[str, str] = {
    "platform": "AethOS",
    "orchestrator": "AethOS Orchestrator",
    "worker": "Runtime Worker",
    "provider": "Provider Brain",
    "setup": "Enterprise Setup",
    "mission_control": "Mission Control",
    "routing": "Advisory Routing",
    "governance": "Operational Governance",
}


def build_runtime_identity_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    base = build_runtime_identity(truth)
    return {
        "runtime_identity_lock": {
            "platform": "AethOS",
            "locked": True,
            "canonical_labels": dict(CANONICAL_LABELS),
            "operational_terminology": dict(OPERATIONAL_TERMINOLOGY),
            "tone": "enterprise_calm",
            "user_facing_brand": "AethOS",
            "legacy_aliases_internal_only": True,
        },
        "runtime_identity": {**base, "terminology_version": "phase4_step10", "brand": "AethOS"},
    }
