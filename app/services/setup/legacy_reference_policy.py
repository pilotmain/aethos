# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Legacy reference classification policy (Phase 4 Step 20)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SEVERITY_LEVELS = ("critical", "operator_visible", "internal_only", "allowed")

CLASSIFICATION_RULES: list[dict[str, Any]] = [
    {"pattern": "Nexa", "path_contains": "tests/test_openclaw", "classification": "allowed", "severity": "allowed"},
    {"pattern": "OpenClaw", "path_contains": "docs/OPENCLAW", "classification": "allowed_parity_doc", "severity": "allowed"},
    {"pattern": "NEXA_", "path_contains": ".env", "classification": "allowed_compat_alias", "severity": "allowed"},
    {"pattern": "Nexa", "path_contains": "web/", "classification": "must_replace_ui", "severity": "operator_visible"},
    {"pattern": "ClawHub", "path_contains": "web/", "classification": "must_replace_ui", "severity": "critical"},
    {"pattern": "Nexa", "path_contains": "aethos_cli/", "classification": "must_replace_operator_surface", "severity": "operator_visible"},
]


def classify_legacy_reference(*, pattern: str, filepath: str) -> dict[str, str]:
    for rule in CLASSIFICATION_RULES:
        if rule["pattern"] in pattern and rule["path_contains"] in filepath:
            return {"classification": rule["classification"], "severity": rule["severity"]}
    if "docs/" in filepath and "OPENCLAW" not in filepath.upper():
        return {"classification": "must_replace_docs", "severity": "internal_only"}
    return {"classification": "internal_only", "severity": "internal_only"}


def build_legacy_reference_policy(*, repo_root: Path | None = None) -> dict[str, Any]:
    return {
        "legacy_reference_policy": {
            "severity_levels": list(SEVERITY_LEVELS),
            "rules": CLASSIFICATION_RULES,
            "preserved": ["NEXA_* env aliases", "parity tests", "README inspiration line"],
            "document": "docs/LEGACY_REFERENCE_POLICY.md",
            "phase": "phase4_step20",
            "bounded": True,
        }
    }
