# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Setup experience final lock (Phase 4 Step 16)."""

from __future__ import annotations

from typing import Any

from app.services.setup.setup_experience import build_setup_experience

GLOBAL_COMMANDS = (
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


def build_setup_experience_final() -> dict[str, Any]:
    base = build_setup_experience()
    exp = base.get("setup_experience") or {}
    exp["global_commands"] = list(GLOBAL_COMMANDS)
    exp["recommended_setup_available"] = True
    exp["show_current_config"] = True
    exp["phase"] = "phase4_step16"
    return {"setup_experience_final": exp, "setup_experience": exp}
