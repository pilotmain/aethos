# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Conversational setup copy and resume UX (Phase 4 Step 15)."""

from __future__ import annotations

from aethos_cli.ui import confirm, print_box, print_info, select


def print_welcome_back_resume() -> str:
    """Ask how to continue after interruption. Returns: continue | review | restart."""
    print_box(
        "Welcome back",
        [
            "AethOS saved your progress.",
            "Continue where you left off, review configuration, or restart onboarding.",
        ],
    )
    choice = select(
        "How would you like to proceed?",
        [
            ("Continue setup", "continue", "Recommended"),
            ("Review saved progress only", "review", "Shows what is already configured"),
            ("Restart onboarding", "restart", "Clears saved wizard state"),
        ],
        default_index=0,
    )
    return choice


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


def print_global_setup_commands() -> None:
    print_info("During setup you can type: help · back · skip · status · resume · retry · exit")


def calm_provider_validation_failed(provider: str) -> str:
    return (
        f"AethOS could not validate {provider} yet. "
        "You can retry now or continue setup and configure it later."
    )
