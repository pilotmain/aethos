# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control first-run guided experience (Phase 4 Step 10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _profile() -> dict[str, Any]:
    path = Path.home() / ".aethos" / "onboarding_profile.json"
    if not path.is_file():
        return {}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob.get("profile") if isinstance(blob, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _tour_state() -> dict[str, Any]:
    try:
        from aethos_cli.setup_completion_guidance import load_tour_state

        return load_tour_state()
    except Exception:
        path = Path.home() / ".aethos" / "mission_control_tour.json"
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}


def mark_mission_control_tour_complete() -> None:
    path = Path.home() / ".aethos" / "mission_control_tour.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {"requested": True, "completed": True, "dismissed": False}
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def mark_mission_control_tour_dismissed() -> None:
    path = Path.home() / ".aethos" / "mission_control_tour.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {"requested": True, "completed": False, "dismissed": True}
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def build_mission_control_first_run(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    profile = _profile()
    tour = _tour_state()
    from app.services.setup.first_run_operator_onboarding import (
        build_first_run_onboarding_prompt,
        needs_first_run_operator_onboarding,
    )

    onboarding = build_first_run_onboarding_prompt()
    setup_complete = Path.home() / ".aethos" / "onboarding_profile.json"
    tour_active = bool(tour.get("requested")) and not tour.get("completed") and not tour.get("dismissed")
    first_run_pending = needs_first_run_operator_onboarding()
    return {
        "mission_control_first_run": {
            "welcome": _welcome_message(profile, first_run_pending=first_run_pending),
            "first_run_onboarding_pending": first_run_pending,
            "first_run_onboarding": onboarding.get("first_run_operator_onboarding"),
            "guided_tour": {
                "active": tour_active,
                "completed": bool(tour.get("completed")),
                "dismissed": bool(tour.get("dismissed")),
                "topics": [
                    {"id": "welcome", "title": "Welcome to AethOS", "path": "/mission-control/onboarding"},
                    {"id": "office", "title": "Office — your operational home", "path": "/mission-control/office"},
                    {"id": "runtime", "title": "Runtime orchestration — live coordination", "path": "/mission-control/runtime-overview"},
                    {"id": "workers", "title": "Workers — agent ecosystem", "path": "/mission-control/workers"},
                    {"id": "philosophy", "title": "Mission Control — calm operational command", "path": "/mission-control/office"},
                    {"id": "providers", "title": "Routing and providers", "path": "/mission-control/providers"},
                    {"id": "governance", "title": "Governance and recovery", "path": "/mission-control/governance"},
                ],
            },
            "steps": [
                {"id": "office", "title": "Office", "path": "/mission-control/office"},
                {"id": "runtime_overview", "title": "Runtime overview", "path": "/mission-control/runtime-overview"},
                {"id": "providers", "title": "Provider setup", "path": "/mission-control/providers"},
                {"id": "workspace", "title": "Workspace", "path": "/mission-control/workspace-intelligence"},
                {"id": "plugins", "title": "Plugins", "path": "/mission-control/plugins"},
                {"id": "privacy", "title": "Privacy posture", "path": "/mission-control/privacy"},
                {"id": "readiness", "title": "Operational readiness", "path": "/mission-control/executive-overview"},
            ],
            "personalized": bool(profile),
            "display_name": profile.get("display_name"),
            "first_run_complete": setup_complete.is_file() and bool(truth.get("runtime_readiness_score")),
            "tone": "premium_calm",
            "bounded": True,
        },
        "operational_readiness_summary": {
            "production_ready": (truth.get("production_runtime_posture") or {}).get("ready"),
            "readiness_score": truth.get("runtime_readiness_score"),
            "calm": (truth.get("calmness_integrity") or {}).get("calm") if isinstance(truth.get("calmness_integrity"), dict) else None,
        },
    }


def _welcome_message(profile: dict[str, Any], *, first_run_pending: bool = False) -> str:
    if first_run_pending:
        return (
            "Welcome — I'm AethOS. I coordinate runtime workers, providers, governance, and operational systems. "
            "Before we begin, share how you work so I can adapt over time."
        )
    name = profile.get("display_name") or profile.get("user_address")
    if name:
        return f"Welcome to AethOS, {name}. Your orchestrator coordinates workers, providers, and governance from one calm surface."
    return "Welcome to AethOS. Mission Control is your operational surface — Office, runtime, workers, and governance in one place."


__all__ = [
    "build_mission_control_first_run",
    "mark_mission_control_tour_complete",
    "mark_mission_control_tour_dismissed",
]
