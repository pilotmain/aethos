# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final branding convergence report (Phase 4 Step 16)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding
from app.services.setup.ui_branding_purge_final import scan_ui_branding_final

OPERATOR_GLOBS = ("aethos_cli/*.py", "web/app/**/*.tsx", "web/lib/**/*.ts", "app/api/**/*.py")


def build_branding_convergence_final(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    cli = scan_user_facing_branding(repo_root=root)
    ui = scan_ui_branding_final(repo_root=root)
    return {
        "branding_convergence_final": {
            "cli_violation_count": len(cli.get("violations") or []),
            "ui_violation_count": len(ui.get("nexa_ui_violations") or []),
            "converged": cli.get("clean") and len(ui.get("nexa_ui_violations") or []) <= 5,
            "targets": list(OPERATOR_GLOBS),
            "disallowed_operator_visible": ["Nexa", "OpenClaw", "ClawHub", "OpenHub"],
            "preserved_compatibility": ["NEXA_* env", "parity tests", "README inspiration"],
            "phase": "phase4_step17",
            "bounded": True,
        }
    }
