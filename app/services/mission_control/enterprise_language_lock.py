# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational language lock (Phase 4 Step 16)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import (
    USER_FACING_TERMS,
    build_mission_control_language_system,
)


CANONICAL_TERMS = {
    "workers": "Runtime workers (orchestrator-supervised specialists)",
    "plugins": "Operational plugins (runtime extensions)",
    "marketplace_skills": "Marketplace skills (AI execution capabilities)",
    "orchestrator": "AethOS orchestrator (coordination authority)",
    "providers": "Reasoning providers (interchangeable engines)",
    "agents": "Use workers or orchestrator — avoid mixed agent jargon in UI",
}


def build_enterprise_language_lock() -> dict[str, Any]:
    lang = build_mission_control_language_system()
    return {
        "enterprise_language_lock": {
            "canonical_terms": CANONICAL_TERMS,
            "user_facing_terms_count": len(USER_FACING_TERMS),
            "language_system": lang.get("mission_control_language_system"),
            "mixed_terminology_disallowed": ["nexa product name in UI", "openclaw in operator copy"],
            "narration_consistency": True,
            "phase": "phase4_step16",
            "bounded": True,
        }
    }
