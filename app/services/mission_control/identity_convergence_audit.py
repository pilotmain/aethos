# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final identity convergence audit (Phase 4 Step 14)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding
from app.services.setup.ui_branding_purge_final import scan_ui_branding_final


def build_identity_convergence_audit(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    cli = scan_user_facing_branding(repo_root=root)
    ui = scan_ui_branding_final(repo_root=root)
    ui_violations = len(ui.get("nexa_ui_violations") or [])
    cli_violations = len(cli.get("violations") or [])
    return {
        "identity_convergence_audit": {
            "user_facing_brand": "AethOS",
            "cli_violation_count": cli_violations,
            "ui_violation_count": ui_violations,
            "convergence_complete": cli.get("clean") and ui_violations <= 5,
            "allowed_nexa": ["NEXA_* env aliases", "migration internals"],
            "allowed_openclaw": ["README inspiration", "parity docs/tests"],
            "disallowed_in_ui": ["Nexa", "OpenHub", "ClawHub", "legacy onboarding labels"],
            "phase": "phase4_step14",
            "bounded": True,
        },
        "branding_scans": {"cli": cli, "ui": ui},
    }
