# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime branding audit for operator surfaces (Phase 4 Step 16)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding
from app.services.setup.setup_branding_convergence import build_setup_branding_convergence
from app.services.setup.ui_branding_purge_final import scan_ui_branding_final


def build_runtime_branding_audit(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    cli = scan_user_facing_branding(repo_root=root)
    ui = scan_ui_branding_final(repo_root=root)
    setup = build_setup_branding_convergence(repo_root=root)
    return {
        "runtime_branding_audit": {
            "cli_violations": len(cli.get("violations") or []),
            "ui_violations": len(ui.get("nexa_ui_violations") or []),
            "cli_clean": cli.get("clean"),
            "ui_acceptable": len(ui.get("nexa_ui_violations") or []) <= 5,
            "operator_surfaces_targeted": True,
            "allowed_openclaw": ["README", "parity docs/tests"],
            "allowed_nexa": ["NEXA_* env aliases", "migration internals"],
            "convergence_phase": "phase4_step16",
            "setup_branding": setup.get("setup_branding_convergence"),
            "bounded": True,
        }
    }
