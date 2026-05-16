# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 16 — enterprise setup finalization and branding convergence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.mission_control.enterprise_language_lock import build_enterprise_language_lock
from app.services.mission_control.runtime_bootstrap import build_runtime_bootstrap
from app.services.mission_control.runtime_branding_audit import build_runtime_branding_audit
from app.services.mission_control.runtime_startup_experience import (
    build_runtime_hydration_stages,
    build_runtime_readiness,
    build_runtime_startup_experience,
)
from app.services.setup.branding_convergence_final import build_branding_convergence_final
from app.services.setup.enterprise_setup_doctor import build_enterprise_setup_doctor
from app.services.setup.setup_experience_final import build_setup_experience_final


def build_runtime_compatibility() -> dict[str, Any]:
    from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities

    caps = build_runtime_capabilities()
    return {
        "runtime_compatibility": {
            "mc_compatibility_version": caps.get("mc_compatibility_version"),
            "feature_flags": caps.get("feature_flags"),
            "route_count": len(caps.get("available_routes") or []),
            "bounded": True,
        }
    }


def apply_runtime_evolution_step16_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    root = Path.cwd()
    truth.update(build_runtime_startup_experience(truth))
    truth.update(build_runtime_hydration_stages(truth))
    truth.update(build_runtime_readiness(truth))
    truth.update(build_runtime_bootstrap(repo_root=root))
    truth.update(build_runtime_compatibility())
    truth.update(build_runtime_branding_audit(repo_root=root))
    truth.update(build_enterprise_language_lock())
    truth.update(build_setup_experience_final())
    truth["enterprise_setup_doctor"] = build_enterprise_setup_doctor(repo_root=root)
    truth["branding_convergence_final"] = build_branding_convergence_final(repo_root=root)
    truth["phase4_step16"] = True
    truth["enterprise_setup_finalized"] = True
    return truth
