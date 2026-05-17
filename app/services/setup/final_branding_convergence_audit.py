# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final branding convergence audit with severity classification (Phase 4 Step 21)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.branding_purge import scan_user_facing_branding
from app.services.setup.legacy_reference_policy import classify_legacy_reference
from app.services.setup.ui_branding_purge_final import scan_ui_branding_final

CLASSIFICATIONS = (
    "operator_critical",
    "operator_visible",
    "compatibility_required",
    "parity_required",
    "historical_allowed",
    "internal_only",
)


def _classify_violation(path: str, term: str) -> str:
    c = classify_legacy_reference(pattern=term, filepath=path)
    sev = c.get("severity", "internal_only")
    if sev == "critical":
        return "operator_critical"
    if sev in ("operator_visible", "must_replace_ui", "must_replace_operator_surface"):
        return "operator_visible"
    if "test_openclaw" in path or "OPENCLAW" in path.upper():
        return "parity_required"
    if "NEXA_" in path or ".env" in path or "config.py" in path:
        return "compatibility_required"
    if path.startswith("docs/"):
        return "historical_allowed"
    return "internal_only"


def build_final_branding_convergence_audit(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    base = scan_user_facing_branding(repo_root=root)
    ui = scan_ui_branding_final(repo_root=root)
    by_class: dict[str, int] = {k: 0 for k in CLASSIFICATIONS}
    operator_visible: list[dict[str, str]] = []
    for v in list(base.get("violations") or []) + list(ui.get("nexa_ui_violations") or []):
        term = v.get("term") or v.get("pattern") or "legacy"
        path = v.get("path") or ""
        cls = _classify_violation(path, term)
        by_class[cls] = by_class.get(cls, 0) + 1
        if cls in ("operator_critical", "operator_visible"):
            operator_visible.append({"path": path, "term": term, "classification": cls})
    op_count = by_class.get("operator_critical", 0) + by_class.get("operator_visible", 0)
    return {
        "final_branding_convergence_audit": {
            "operator_visible_legacy_refs": op_count,
            "near_zero_operator_goal": op_count <= 5,
            "by_classification": by_class,
            "operator_violations_sample": operator_visible[:25],
            "cli_clean": base.get("clean"),
            "ui_clean": ui.get("clean"),
            "phase": "phase4_step21",
            "bounded": True,
        }
    }
