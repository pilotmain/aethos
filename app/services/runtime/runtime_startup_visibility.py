# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Calm startup orchestration UX (Phase 4 Step 28)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_launch_experience import build_runtime_launch_experience


def build_runtime_startup_visibility(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    launch = build_runtime_launch_experience(truth)
    exp = launch.get("runtime_launch_experience") or {}
    in_progress = not exp.get("truly_operational")
    headline = (
        "Enterprise runtime startup is still in progress."
        if in_progress
        else "Operational startup completed."
    )
    return {
        "runtime_startup_visibility": {
            "phase": "phase4_step28",
            "headline": headline,
            "banner": "AethOS is preparing operational services." if in_progress else "Enterprise runtime operational.",
            "startup_in_progress": in_progress,
            "no_duplicate_narratives": True,
            "no_panic": True,
            "progressive_unlock": ["office", "runtime_overview", "governance", "runtime_intelligence"],
            "bounded": True,
        }
    }


def build_runtime_startup_status(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    launch = build_runtime_launch_experience(truth)
    return {
        "runtime_startup_status": {
            "phase": "phase4_step28",
            "stage": (launch.get("runtime_launch_experience") or {}).get("current_stage"),
            "readiness": launch.get("runtime_launch_readiness"),
            "integrity": launch.get("runtime_launch_integrity"),
            "bounded": True,
        }
    }
