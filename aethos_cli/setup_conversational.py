# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Conversational setup copy and resume UX (Phase 4 Step 15)."""

from __future__ import annotations

from aethos_cli.ui import confirm, print_box, print_info, select


def print_existing_routing_review(*, mode: str, preference: str, mission_control: bool = False) -> str:
    """When routing already configured. Returns: keep | adjust | rebuild."""
    from aethos_cli.setup_routing import canonical_routing_label, canonical_routing_summary

    lines = [
        "AethOS already configured your local runtime routing.",
        "",
        "Current strategy:",
        f"• {canonical_routing_label(mode)}",
        f"• {canonical_routing_summary(mode, preference)}",
    ]
    if mission_control:
        lines.append("• Mission Control linked")
    print_box("Existing configuration", lines)
    return select(
        "Would you like to:",
        [
            ("Keep this configuration", "keep", "Continue setup with current routing"),
            ("Improve or adjust it", "adjust", "Re-run routing section"),
            ("Rebuild setup from scratch", "rebuild", "Clear wizard state"),
        ],
        default_index=0,
    )


def print_existing_setup_menu() -> str:
    """When install already exists. Returns: continue | review | section | restart."""
    print_box(
        "AethOS found an existing setup",
        [
            "What would you like to do?",
            "Continue — resume saved progress",
            "Review — inspect current configuration",
            "Change one section — adjust routing, providers, Mission Control, …",
            "Restart — clear wizard state and run fresh",
        ],
    )
    return select(
        "How would you like to proceed?",
        [
            ("Continue where I left off", "continue", "Recommended"),
            ("Review current configuration", "review", "Read-only summary"),
            ("Change one section", "section", "Pick a section to reconfigure"),
            ("Restart setup", "restart", "Clears saved wizard state"),
        ],
        default_index=0,
    )


def print_welcome_back_resume() -> str:
    """Ask how to continue after interruption. Returns: continue | review | section | restart."""
    return print_existing_setup_menu()


def print_change_one_section_menu() -> str | None:
    """Return section id to re-run, or None to skip."""
    return select(
        "Which section would you like to change?",
        [
            ("Runtime strategy", "runtime_strategy", "Local / cloud / hybrid"),
            ("Providers & API keys", "providers", "LLM providers"),
            ("Channels", "channels", "Telegram and messaging"),
            ("Mission Control connection", "mission_control", "Bearer token and web env"),
            ("Workspace", "workspace", "Project workspace path"),
            ("Onboarding profile", "onboarding", "Operator preferences"),
            ("Web search", "web_search", "Search provider"),
            ("Integrations", "integrations", "Detected integrations"),
            ("Privacy", "privacy", "Privacy posture"),
            ("Skip — return to setup", "skip", ""),
        ],
        default_index=9,
    )


def print_runtime_strategy_guidance() -> None:
    print_box(
        "Runtime strategy",
        [
            "AethOS routes work to the best available reasoning engine.",
            "Local-first — privacy on your machine (Ollama).",
            "Cloud-first — powerful APIs when keys are configured.",
            "Hybrid — intelligent routing with calm fallback.",
            "Configure later — operational bootstrap first.",
        ],
    )


SETUP_GLOBAL_COMMANDS = (
    "help",
    "why",
    "skip",
    "back",
    "resume",
    "status",
    "recommended",
    "current",
    "repair",
    "quit",
)


def print_global_setup_commands() -> None:
    print_info("Commands: " + " · ".join(SETUP_GLOBAL_COMMANDS))


def print_setup_help() -> None:
    print_box(
        "Setup help",
        [
            "why — explain this step",
            "skip — defer (configure later)",
            "back — previous step when available",
            "status — show saved progress",
            "recommended — accept recommended defaults",
            "current — show current configuration",
            "repair — run setup repair",
            "quit — exit safely (progress saved)",
        ],
    )


def handle_setup_global_command(cmd: str) -> bool:
    """Return True if handled (caller should re-prompt)."""
    c = (cmd or "").strip().lower()
    if c == "help":
        print_setup_help()
        return True
    if c == "why":
        print_info("Each step configures how AethOS orchestrates workers, providers, and Mission Control.")
        return True
    if c in ("status", "current"):
        from app.services.setup.setup_continuity import build_setup_continuity

        cont = build_setup_continuity()
        print_info(cont["setup_continuity"].get("welcome_back_message", "No saved state"))
        return True
    if c == "recommended":
        print_info("Recommended: hybrid routing, seed Mission Control, calm operational defaults.")
        return True
    if c == "repair":
        print_info("Run: aethos setup repair (after this wizard if needed)")
        return True
    return False


def calm_provider_validation_failed(provider: str) -> str:
    return (
        f"AethOS could not validate {provider} yet. "
        "You can retry now or continue setup and configure it later."
    )
