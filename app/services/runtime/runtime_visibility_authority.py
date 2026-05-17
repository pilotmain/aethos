# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Single authoritative operational visibility model (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_unified_narrative_engine import build_runtime_unified_narrative_engine


def build_runtime_visibility_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    narrative = build_runtime_unified_narrative_engine(truth)
    readiness = truth.get("runtime_readiness_convergence") or {}
    return {
        "runtime_visibility_authority": {
            "phase": "phase4_step27",
            "authoritative": True,
            "domains": [
                "readiness",
                "degraded_mode",
                "recovery",
                "startup",
                "hydration",
                "supervision",
                "trust",
                "operational_status",
            ],
            "headline": narrative.get("runtime_unified_narrative"),
            "readiness_state": readiness.get("canonical_state"),
            "calm": True,
            "progressive": True,
            "bounded": True,
            "explainable": True,
            "non_duplicated": True,
        }
    }
