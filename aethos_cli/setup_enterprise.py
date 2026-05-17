# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup extensions — Phase 4 Step 4."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aethos_cli.setup_channels import CHANNELS, configure_channel_choice
from aethos_cli.setup_conversational import build_existing_config_summary, prompt_section_review
from aethos_cli.setup_health import run_setup_health_checks
from aethos_cli.setup_integrations_detect import detect_integrations
from aethos_cli.setup_interactive_mode import setup_interactive
from aethos_cli.setup_mission_control import seed_mission_control_connection
from aethos_cli.setup_onboarding_profile import (
    load_onboarding_profile,
    run_onboarding_profile_questions,
    save_onboarding_profile,
)
from aethos_cli.setup_ready_state_semantics import build_setup_completion_card
from aethos_cli.setup_routing import CANONICAL_ROUTING_MODES, build_routing_env_updates, routing_summary
from aethos_cli.setup_web_search import PROVIDERS, configure_web_search
from aethos_cli.setup_prompt_runtime import prompt_confirm as confirm, prompt_select as select, set_prompt_context
from aethos_cli.ui import print_box, print_info, print_step, print_success


def _section_targeted(bag: dict[str, Any], section_id: str) -> bool:
    target = bag.get("section_rerun")
    if not target:
        return True
    return target == section_id


def _interactive_review(section_id: str, title: str, lines: list[str], bag: dict[str, Any]) -> bool:
    """Return True if section should run (change or not configured)."""
    if bag.get("section_rerun") == section_id:
        return True
    if not setup_interactive() or bag.get("review_each_section") is not True:
        return True
    action = prompt_section_review(title, lines)
    if action == "keep":
        return False
    if action == "skip":
        bag.setdefault("skipped_sections", []).append(section_id)
        return False
    return True


def _routing_summary_lines(repo_root: Path) -> list[str]:
    env = build_existing_config_summary(repo_root=repo_root)
    return [line for line in env if line.startswith("Strategy") or line.startswith("Routing")]


def _advanced_options_enabled(bag: dict[str, Any]) -> bool:
    if "advanced_options" in bag:
        return bool(bag["advanced_options"])
    if not setup_interactive():
        bag["advanced_options"] = False
        return False
    enabled = confirm("Advanced options? (LiteLLM, OpenRouter, custom gateways, deep governance)", default=False)
    bag["advanced_options"] = enabled
    return enabled


def run_enterprise_setup_extensions(
    *,
    repo_root: Path,
    updates: dict[str, str],
    api_base: str,
    bag: dict[str, Any],
) -> dict[str, Any]:
    """Run Phase 4 Step 4 sections; merge env updates into ``updates``."""
    if _section_targeted(bag, "runtime_strategy") and _interactive_review(
        "runtime_strategy", "Runtime strategy", _routing_summary_lines(repo_root), bag
    ):
        set_prompt_context(section="runtime_strategy")
        print_step("5b", "Runtime strategy")
        route_opts = [
            (CANONICAL_ROUTING_MODES["local_only"]["label"], "local_only", CANONICAL_ROUTING_MODES["local_only"]["tradeoff"]),
            (CANONICAL_ROUTING_MODES["cloud_only"]["label"], "cloud_only", CANONICAL_ROUTING_MODES["cloud_only"]["tradeoff"]),
            (CANONICAL_ROUTING_MODES["hybrid"]["label"], "hybrid", CANONICAL_ROUTING_MODES["hybrid"]["tradeoff"]),
            (CANONICAL_ROUTING_MODES["later"]["label"], "later", CANONICAL_ROUTING_MODES["later"]["tradeoff"]),
        ]
        mode = select("How should AethOS think and route work?", route_opts, default_index=2)
        pref_opts = [
            ("Balanced", "balanced", "Recommended default"),
            ("Quality-first", "best_quality", "Prefer strongest models"),
            ("Cost-first", "lowest_cost", "Minimize paid usage"),
            ("Privacy-first", "local_first", "Prefer local models"),
            ("Ask before paid fallback", "balanced", "Approval gate on paid providers"),
        ]
        pref = select("How should AethOS choose models?", pref_opts, default_index=0)
        paid_ok = confirm("Require approval before paid provider fallback?", default=True)
        updates.update(build_routing_env_updates(mode, preference=pref, require_paid_fallback_approval=paid_ok))
        bag["routing_mode"] = mode
        bag["routing_preference"] = pref
        bag["routing_summary"] = routing_summary(mode, pref)
        from aethos_cli.setup_conversation_context import get_setup_conversation

        conv = get_setup_conversation()
        conv.record("routing_mode", mode)
        conv.record("routing_preference", pref)
        conv.print_continuity("routing")
        print_success(f"Routing: {bag['routing_summary']}")

    if _section_targeted(bag, "mission_control") and _interactive_review(
        "mission_control",
        "Mission Control",
        [line for line in build_existing_config_summary(repo_root=repo_root) if "Mission Control" in line],
        bag,
    ):
        set_prompt_context(section="mission_control")
        print_step("5c", "Mission Control")
        print_info("Mission Control is the local web UI — bearer token and API URL connect automatically.")
        if confirm("Should AethOS configure Mission Control automatically?", default=True):
            mc_updates = seed_mission_control_connection(repo_root=repo_root, api_base=api_base)
            updates.update(mc_updates)
            bag["mission_control_seeded"] = True
            print_success("Mission Control connection seeded.")

    if _section_targeted(bag, "channels") and _interactive_review(
        "channels", "Channels", ["Default: Web UI only unless you enable messaging"], bag
    ):
        set_prompt_context(section="channels")
        if confirm("Configure a communication channel now? (default: Web UI only)", default=False):
            print_step("5d", "Communication channel")
            ch_opts = [(a, b, c) for a, b, c, _ in CHANNELS]
            ch = select("Channel", ch_opts, default_index=len(ch_opts) - 1)
            configure_channel_choice(ch, updates)

    if _section_targeted(bag, "web_search") and _advanced_options_enabled(bag):
        if confirm("Configure a web search provider?", default=False):
            print_step("5e", "Web search")
            ws_opts = [(a, b, "") for a, b, _ in PROVIDERS]
            ws = select("Web search provider", ws_opts, default_index=len(ws_opts) - 1)
            configure_web_search(ws, updates)

    if _section_targeted(bag, "integrations") and _advanced_options_enabled(bag):
        print_step("5f", "Provider integrations")
        integrations = detect_integrations()
        lines = [f"{'✓' if v else '○'} {k}" for k, v in integrations.get("installed", {}).items()]
        print_box("Detected CLIs", lines)
        bag["integrations"] = integrations

    if _section_targeted(bag, "onboarding"):
        set_prompt_context(section="onboarding")
        existing = load_onboarding_profile()
        run_onboarding = True
        if existing and setup_interactive():
            preview = [
                f"Name: {existing.get('display_name') or '—'}",
                f"Assistant: {existing.get('assistant_name') or 'AethOS'}",
                f"Tone: {existing.get('tone') or '—'}",
            ]
            action = prompt_section_review("Onboarding profile", preview)
            if action == "keep":
                run_onboarding = False
                bag["onboarding_profile"] = existing
            elif action == "skip":
                run_onboarding = False
        if run_onboarding:
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
    truly_operational: bool | None = None,
    mission_control_expected: bool = True,
) -> None:
    """Health checks + honest completion card."""
    print_step("6", "Health checks")
    health = run_setup_health_checks(repo_root=repo_root, api_base=api_base)
    lines = []
    for c in health.get("checks") or []:
        sym = "✓" if c.get("ok") else "✗"
        lines.append(f"{sym} {c.get('name')}: {c.get('detail')}")
    print_box("Setup health", lines)
    bag["health"] = health

    if truly_operational is None:
        truly_operational = bool(bag.get("startup_result", {}).get("truly_operational"))

    api_ok = any(c.get("name") == "api_health" and c.get("ok") for c in health.get("checks") or [])
    mc_ok = any(c.get("name") == "mission_control" and c.get("ok") for c in health.get("checks") or [])

    if setup_interactive() and not api_ok:
        from aethos_cli.setup_actionable_recovery import prompt_service_start, try_start_api

        port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
        if prompt_service_start("Start API", default_yes=True):
            try_start_api(repo_root=repo_root, port=port)
            health = run_setup_health_checks(repo_root=repo_root, api_base=api_base)
            bag["health"] = health
            api_ok = any(c.get("name") == "api_health" and c.get("ok") for c in health.get("checks") or [])

    if setup_interactive() and mission_control_expected and not mc_ok:
        from aethos_cli.setup_actionable_recovery import prompt_service_start, try_start_mission_control

        if prompt_service_start("Start Mission Control", default_yes=True):
            try_start_mission_control(repo_root=repo_root)
            health = run_setup_health_checks(repo_root=repo_root, api_base=api_base)
            bag["health"] = health
            mc_ok = any(c.get("name") == "mission_control" and c.get("ok") for c in health.get("checks") or [])

    truly_operational = truly_operational or (api_ok and (mc_ok or not mission_control_expected))
    title, card_lines = build_setup_completion_card(
        health=health,
        api_base=api_base,
        bag=bag,
        truly_operational=truly_operational,
        mission_control_expected=mission_control_expected,
        startup_result=bag.get("startup_result"),
    )
    print_box(title, card_lines)
