# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime surface authority map and registries (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_surface_consolidation import SURFACE_RESPONSIBILITIES


def build_runtime_surface_authority_map() -> dict[str, Any]:
    authoritative = ["office", "runtime_overview", "runtime_supervision", "governance"]
    deprecated = ["operational_insights"]
    aliases = {"operational_insights": "runtime_intelligence"}
    return {
        "runtime_surface_authority_map": {
            "authoritative": authoritative,
            "office_entry": "office",
            "bounded": True,
        },
        "surface_responsibility_registry": dict(SURFACE_RESPONSIBILITIES),
        "deprecated_surface_registry": {d: f"Use {aliases.get(d, 'runtime_intelligence')}" for d in deprecated},
        "phase": "phase4_step23",
        "bounded": True,
    }
