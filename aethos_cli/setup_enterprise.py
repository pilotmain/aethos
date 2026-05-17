# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup extensions — Phase 4 Step 4."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aethos_cli.setup_channels import CHANNELS, configure_channel_choice
from aethos_cli.setup_health import run_setup_health_checks
from aethos_cli.setup_integrations_detect import detect_integrations
from aethos_cli.setup_mission_control import seed_mission_control_connection
from aethos_cli.setup_onboarding_profile import run_onboarding_profile_questions, save_onboarding_profile
from aethos_cli.setup_routing import build_routing_env_updates, routing_summary
from aethos_cli.setup_web_search import PROVIDERS, configure_web_search
from aethos_cli.setup_prompt_runtime import prompt_confirm as confirm, prompt_select as select
from aethos_cli.ui import print_box, print_info, print_step, print_success


def run_enterprise_setup_extensions(
    *,
    repo_root: Path,
    updates: dict[str, str],
    api_base: str,
    bag: dict[str, Any],
) -> dict[str, Any]:
    """Run Phase 4 Step 4 sections; merge env updates into ``updates``."""
    print_step("5b", "Intelligence routing")
    route_opts = [
        ("Local only (Ollama / private)", "local_only", "No cloud LLM by default"),
        ("Cloud provider only", "cloud_only", "API keys required"),
        ("Hybrid / local-first", "hybrid", "Local when possible, cloud fallback"),
        ("Ask later", "later", "Configure routing after setup"),
    ]
    mode = select("How should AethOS route intelligence?", route_opts, default_index=2)
    pref_opts = [
        ("Best quality", "best_quality", ""),
        ("Lowest cost", "lowest_cost", ""),
        ("Local-first", "local_first", ""),
        ("Balanced", "balanced", "Recommended"),
    ]
    pref = select("Routing preference", pref_opts, default_index=3)
    paid_ok = confirm("Require approval before paid provider fallback?", default=True)
    updates.update(build_routing_env_updates(mode, preference=pref, require_paid_fallback_approval=paid_ok))
    bag["routing_mode"] = mode
    bag["routing_summary"] = routing_summary(mode, pref)
    print_success(f"Routing: {bag['routing_summary']}")

    print_step("5c", "Mission Control connection")
    mc_updates = seed_mission_control_connection(repo_root=repo_root, api_base=api_base)
    updates.update(mc_updates)
    bag["mission_control_seeded"] = True

    if confirm("Configure a communication channel now?", default=False):
        print_step("5d", "Communication channel")
        ch_opts = [(a, b, c) for a, b, c, _ in CHANNELS]
        ch = select("Channel", ch_opts, default_index=len(ch_opts) - 1)
        configure_channel_choice(ch, updates)

    if confirm("Configure a web search provider?", default=False):
        print_step("5e", "Web search")
        ws_opts = [(a, b, "") for a, b, _ in PROVIDERS]
        ws = select("Web search provider", ws_opts, default_index=len(ws_opts) - 1)
        configure_web_search(ws, updates)

    print_step("5f", "Provider integrations")
    integrations = detect_integrations()
    lines = [f"{'✓' if v else '○'} {k}" for k, v in integrations.get("installed", {}).items()]
    print_box("Detected CLIs", lines)
    bag["integrations"] = integrations

    if confirm("Orchestrator onboarding (recommended)?", default=True):
        print_step("5g", "Orchestrator onboarding")
        from aethos_cli.setup_orchestrator_onboarding import run_orchestrator_onboarding

        profile = run_orchestrator_onboarding()
        bag["onboarding_profile"] = profile
    elif confirm("Quick profile only (name, goals, tone)?", default=False):
        print_step("5g", "First-run profile")
        profile = run_onboarding_profile_questions()
        if profile:
            save_onboarding_profile(profile)
            bag["onboarding_profile"] = profile

    return bag


def print_setup_final_summary(
    *,
    repo_root: Path,
    api_base: str,
    bag: dict[str, Any],
) -> None:
    """Health checks + final summary card."""
    print_step("6", "Health checks")
    health = run_setup_health_checks(repo_root=repo_root, api_base=api_base)
    lines = []
    for c in health.get("checks") or []:
        sym = "✓" if c.get("ok") else "✗"
        lines.append(f"{sym} {c.get('name')}: {c.get('detail')}")
    print_box("Setup health", lines)
    bag["health"] = health

    mc = "http://localhost:3000"
    print_box(
        "AethOS ready",
        [
            f"Mission Control: {mc}",
            f"API: {api_base}",
            f"API docs: {api_base}/docs",
            f"Routing: {bag.get('routing_summary', 'configured')}",
            "Restart: aethos restart",
            "Repair: aethos setup repair",
            "Doctor: aethos setup doctor",
            "Validate: aethos setup validate",
        ],
    )
