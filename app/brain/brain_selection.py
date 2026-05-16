# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Select the best available brain for a task (Phase 2 Step 7)."""

from __future__ import annotations

import os
from typing import Any

from app.brain.brain_capabilities import REPAIR_PLAN_TASK, brain_is_local
from app.brain.brain_registry import list_repair_brain_candidates
from app.core.config import Settings, get_settings
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode


def _pytest_forced_deterministic() -> bool:
    if (os.environ.get("NEXA_PYTEST") or "").strip() in ("1", "true", "yes"):
        return True
    if (os.environ.get("USE_REAL_LLM") or "").strip().lower() not in ("1", "true", "yes", "on"):
        return True
    return False


def select_brain_for_task(
    task: str,
    *,
    evidence_text: str = "",
    settings: Settings | None = None,
    force_deterministic: bool | None = None,
) -> dict[str, Any]:
    """
    Selection order:
    1. local model when local-first / local-only policy applies
    2. configured primary provider when available
    3. fallback providers from registry
    4. deterministic fallback
    """
    s = settings or get_settings()
    mode = current_privacy_mode(s)
    local_first = bool(s.aethos_local_first_enabled or s.nexa_local_first)
    if force_deterministic is None:
        force_det = _pytest_forced_deterministic()
    else:
        force_det = bool(force_deterministic)

    if force_det or task != REPAIR_PLAN_TASK:
        return {
            "selected_provider": "deterministic",
            "selected_model": "deterministic-repair-v1",
            "local_first": local_first,
            "reason": "tests_or_use_real_llm_disabled",
            "fallback_used": False,
        }

    candidates = list_repair_brain_candidates(s)
    if mode == PrivacyMode.LOCAL_ONLY:
        for row in candidates:
            if row.get("local") and row.get("available"):
                return {
                    "selected_provider": row["provider"],
                    "selected_model": str(row.get("model") or ""),
                    "local_first": True,
                    "reason": "privacy_local_only",
                    "fallback_used": False,
                }
        return {
            "selected_provider": "deterministic",
            "selected_model": "deterministic-repair-v1",
            "local_first": True,
            "reason": "local_only_no_external_brain",
            "fallback_used": True,
        }

    if local_first:
        for row in candidates:
            if row.get("local") and row.get("available"):
                return {
                    "selected_provider": row["provider"],
                    "selected_model": str(row.get("model") or ""),
                    "local_first": True,
                    "reason": "local_first_preference",
                    "fallback_used": False,
                }

    for row in candidates:
        if row.get("available") and row.get("provider") != "deterministic":
            return {
                "selected_provider": row["provider"],
                "selected_model": str(row.get("model") or ""),
                "local_first": local_first,
                "reason": "primary_or_fallback_provider",
                "fallback_used": False,
            }

    return {
        "selected_provider": "deterministic",
        "selected_model": "deterministic-repair-v1",
        "local_first": local_first,
        "reason": "no_external_brain_available",
        "fallback_used": True,
    }


def brain_allows_external_call(selection: dict[str, Any], *, settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    mode = current_privacy_mode(s)
    if mode == PrivacyMode.LOCAL_ONLY:
        return brain_is_local(str(selection.get("selected_provider") or ""))
    if mode == PrivacyMode.BLOCK:
        return brain_is_local(str(selection.get("selected_provider") or ""))
    return True
