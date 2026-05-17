# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime branding audit for operator surfaces (Phase 4 Step 16)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.final_branding_convergence_audit import build_final_branding_convergence_audit
from app.services.setup.setup_branding_convergence import build_setup_branding_convergence


def build_runtime_branding_audit(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    final = build_final_branding_convergence_audit(repo_root=root)
    setup = build_setup_branding_convergence(repo_root=root)
    audit = final.get("final_branding_convergence_audit") or {}
    return {
        "runtime_branding_audit": {
            **audit,
            "operator_visible_legacy_refs": audit.get("operator_visible_legacy_refs"),
            "setup_branding": setup.get("setup_branding_convergence"),
            "convergence_phase": "phase4_step21",
            "bounded": True,
        }
    }
