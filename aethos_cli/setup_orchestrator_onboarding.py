# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Orchestrator-first onboarding conversation (Phase 4 Step 10)."""

from __future__ import annotations

from typing import Any

from aethos_cli.setup_onboarding_profile import save_onboarding_profile
from aethos_cli.ui import get_input, print_box, print_info, print_success


def run_orchestrator_onboarding() -> dict[str, Any]:
    """AethOS introduces itself as orchestrator and collects personalization."""
    print_box(
        "AethOS Orchestrator",
        [
            "I coordinate runtime workers, providers, and Mission Control — I am not the model itself.",
            "Providers are interchangeable brains; I own routing, governance, and operational truth.",
        ],
    )
    print_info("Let's personalize your workspace (Enter skips optional questions).")
    profile: dict[str, Any] = {
        "display_name": (get_input("What should I call you?") or "").strip() or None,
        "user_address": (get_input("How would you like me to address you?") or "").strip() or None,
        "tone": (get_input("Preferred tone (concise/calm/formal/proactive)", "calm") or "calm").strip(),
        "profession": (get_input("What do you do professionally?") or "").strip() or None,
        "goals": (get_input("What are your main goals with AethOS?") or "").strip() or None,
        "interests": (get_input("Topics or interests I should remember?") or "").strip() or None,
        "working_style": (get_input("Preferred working style (async/sync/deep-focus)", "async") or "async").strip(),
        "coding_preference": (get_input("Coding preference (local-first/cloud/hybrid)", "hybrid") or "hybrid").strip(),
        "privacy_preference": (
            get_input("Privacy preference (local-first/balanced/cloud-ok)", "local-first") or "local-first"
        ).strip(),
        "operational_preference": (
            get_input("Operational preference (calm/verbose/advisory)", "calm") or "calm"
        ).strip(),
        "preferred_providers": (get_input("Preferred models/providers (optional)") or "").strip() or None,
        "assistant_name": "AethOS",
        "orchestrator_intro_complete": True,
    }
    profile = {k: v for k, v in profile.items() if v is not None}
    if profile:
        save_onboarding_profile(profile)
    print_success("Onboarding saved — Mission Control will reflect your preferences.")
    return profile
