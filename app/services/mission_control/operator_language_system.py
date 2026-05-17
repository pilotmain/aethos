# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator language system — terminology + calmness (Phase 4 Step 21)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operator_language_guide import build_operator_language_guide
from app.services.mission_control.runtime_calmness_lock import build_runtime_calmness_lock


def build_operator_language_system(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    guide = build_operator_language_guide()["operator_language_guide"]
    calm = build_runtime_calmness_lock(truth)["runtime_calmness_lock"]
    return {
        "operator_language_system": {
            **guide,
            "calmness": calm,
            "unified_terms": list(guide.get("preferred_terms", {}).keys()),
            "phase": "phase4_step21",
            "bounded": True,
        }
    }
