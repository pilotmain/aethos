# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""First-impression ready-state lock bundle (Phase 4 Step 11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding
from app.services.setup.env_completeness import build_env_completeness_audit
from app.services.setup.frontend_contract_lock import build_frontend_backend_contract_lock
from app.services.setup.mission_control_ready_state import build_mission_control_ready_state
from app.services.setup.setup_path_certification import certify_one_curl_path
from app.services.setup.production_cut_readiness import build_production_cut_readiness
from app.services.setup.setup_status import build_setup_status
from app.services.setup.ui_branding_purge_final import scan_ui_branding_final


def build_setup_ready_state_lock(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    path_cert = certify_one_curl_path(repo_root=root)
    status = build_setup_status(repo_root=root)
    mc_ready = build_mission_control_ready_state(repo_root=root)
    env_audit = build_env_completeness_audit(repo_root=root)
    branding = scan_user_facing_branding(repo_root=root)
    ui_branding = scan_ui_branding_final(repo_root=root)
    contract = build_frontend_backend_contract_lock()
    locked = (
        path_cert.get("certified")
        and status.get("complete")
        and branding.get("clean")
        and len(ui_branding.get("nexa_ui_violations") or []) <= 5
        and contract.get("locked")
    )
    return {
        "ready_state_locked": locked,
        "one_curl_certified": path_cert.get("certified"),
        "setup_complete": status.get("complete"),
        "mission_control_ready": mc_ready.get("ready"),
        "branding_clean": branding.get("clean"),
        "contract_locked": contract.get("locked"),
        "runtime_readiness_authority_required": True,
        "runtime_production_certification_required": True,
        "launch_stabilization_required": True,
        "phase": "phase4_step24",
        "production_cut": build_production_cut_readiness(),
        "path_certification": path_cert,
        "setup_status": status,
        "mission_control": mc_ready,
        "env_completeness": env_audit,
        "branding_audit": {"clean": branding.get("clean"), "violation_count": len(branding.get("violations") or [])},
        "ui_branding_audit": ui_branding,
        "frontend_contract": contract,
    }
