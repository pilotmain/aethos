# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 15 — installer and onboarding convergence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.first_impression_certification import build_first_impression_certification
from app.services.setup.installer_recovery_flow import build_installer_recovery_flow
from app.services.setup.runtime_strategy_onboarding import (
    build_provider_routing_explained,
    build_runtime_strategy_onboarding,
)
from app.services.setup.setup_branding_convergence import build_setup_branding_convergence
from app.services.setup.setup_continuity import build_setup_continuity
from app.services.setup.setup_experience import build_setup_experience
from app.services.setup.setup_first_impression import build_setup_first_impression
from app.services.setup.setup_flow_convergence import build_setup_flow_convergence
from app.services.setup.setup_operator_profile_api import build_setup_operator_profile


def apply_runtime_evolution_step15_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    root = Path.cwd()
    truth.update(build_setup_continuity(repo_root=root))
    truth.update(build_setup_experience())
    truth.update(build_setup_operator_profile())
    truth.update(build_setup_first_impression(repo_root=root, truth=truth))
    truth.update(build_runtime_strategy_onboarding())
    truth.update(build_provider_routing_explained())
    truth.update(build_installer_recovery_flow())
    truth.update(build_setup_flow_convergence())
    truth.update(build_setup_branding_convergence(repo_root=root))
    truth["first_impression_certification"] = build_first_impression_certification(repo_root=root)
    truth["phase4_step15"] = True
    truth["first_impression_locked"] = True
    return truth
