# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup coverage report (Phase 4 Step 20)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.env_completeness import SETUP_COVERED_KEYS, build_env_completeness_audit

COVERED_SYSTEMS = (
    "provider_routing",
    "ollama",
    "local_first",
    "hybrid_routing",
    "fallback_chains",
    "mission_control_bootstrap",
    "runtime_cache_tuning",
    "hydration_tuning",
    "process_supervision",
    "telegram_ownership",
    "browser_automation",
    "plugins",
    "marketplace",
    "governance",
    "operational_intelligence",
    "runtime_recovery",
    "office_streaming",
    "onboarding_profile",
    "compatibility_versioning",
)

OPTIONAL_SYSTEMS = ("web_search", "discord", "slack", "paid_provider_approval")


def build_setup_coverage(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    env = build_env_completeness_audit(repo_root=root)
    missing_optional = [s for s in OPTIONAL_SYSTEMS if s not in ("web_search",)]
    return {
        "setup_coverage": {
            "covered_systems": list(COVERED_SYSTEMS),
            "optional_systems": list(OPTIONAL_SYSTEMS),
            "env_keys_covered": len(SETUP_COVERED_KEYS),
            "missing_optional": missing_optional,
            "recommended_enhancements": [
                "Configure web search for research workflows",
                "Run aethos setup doctor after env changes",
            ],
            "env_audit": env,
            "phase": "phase4_step20",
            "bounded": True,
        }
    }
