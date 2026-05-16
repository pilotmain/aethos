# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Installer branding convergence audit (Phase 4 Step 15)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding


INSTALLER_PATHS = (
    "aethos_cli/setup_wizard.py",
    "aethos_cli/setup_orchestrator_onboarding.py",
    "install.sh",
    "scripts/setup.sh",
)


def build_setup_branding_convergence(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    scan = scan_user_facing_branding(repo_root=root)
    return {
        "setup_branding_convergence": {
            "user_facing_brand": "AethOS",
            "installer_paths_audited": list(INSTALLER_PATHS),
            "cli_violations": len(scan.get("violations") or []),
            "converged": scan.get("clean"),
            "disallowed_visible": ["Nexa wizard", "OpenClaw setup", "numbered developer wizard"],
            "allowed_nexa": ["NEXA_* env aliases only"],
            "allowed_openclaw": ["README inspiration", "parity tests only"],
            "phase": "phase4_step15",
            "bounded": True,
        }
    }
