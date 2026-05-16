# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Extended failure classification for repair workflows (Phase 2 Step 6)."""

from __future__ import annotations

import re
from typing import Any

from app.providers.actions.provider_logs import classify_cli_text
from app.providers.provider_privacy import redact_cli_output

_EXTRA_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    ("missing_package_json", (re.compile(r"enoent.*package\.json|missing package\.json", re.I),)),
    ("test_failure", (re.compile(r"test failed|tests failed|jest.*fail|pytest.*fail", re.I),)),
    ("lint_failure", (re.compile(r"eslint|lint error|prettier", re.I),)),
    ("dependency_failure", (re.compile(r"cannot find module|module not found|ERESOLVE|npm err", re.I),)),
    (
        "environment_variable_missing",
        (re.compile(r"env(?:ironment)? variable|process\.env|missing env", re.I),),
    ),
)


def classify_failure_text(text: str) -> str:
    blob = redact_cli_output(text or "", max_out=12_000)
    for label, patterns in _EXTRA_PATTERNS:
        if any(p.search(blob) for p in patterns):
            return label
    base = classify_cli_text(blob)
    if base == "deployment_failure" and "build" in blob.lower():
        return "build_failure"
    if base not in ("ok",):
        return base
    return "unknown"


def diagnose_failure(
    *,
    logs_preview: str = "",
    workspace_signals: list[str] | None = None,
) -> dict[str, Any]:
    merged = logs_preview or ""
    if workspace_signals and "package.json" not in workspace_signals:
        category = "missing_package_json"
    else:
        category = classify_failure_text(merged)
    confidence = 0.85 if category not in ("unknown", "deployment_failure") else 0.55
    suggestions: list[str] = []
    if category == "missing_provider_auth":
        suggestions.append("Run provider login, then aethos providers scan")
    elif category in ("build_failure", "dependency_failure", "test_failure"):
        suggestions.append("Run local verification (npm run build / test) before redeploy")
    elif category == "missing_package_json":
        suggestions.append("Link the correct repo root with aethos projects link")
    return {
        "failure_category": category,
        "confidence": confidence,
        "diagnosis": _diagnosis_line(category),
        "suggested_fix_path": suggestions,
        "needs_workspace_edit": category
        in ("build_failure", "dependency_failure", "test_failure", "lint_failure"),
        "needs_provider_login": category == "missing_provider_auth",
    }


def _diagnosis_line(category: str) -> str:
    return {
        "build_failure": "Build failed — inspect compiler/bundler output.",
        "dependency_failure": "Dependency resolution or install issue detected.",
        "test_failure": "Tests failed in the workspace or CI output.",
        "lint_failure": "Lint/static analysis reported errors.",
        "missing_package_json": "Workspace is missing package.json at the project root.",
        "missing_provider_auth": "Provider CLI is not authenticated.",
        "missing_provider_cli": "Provider CLI is missing on PATH.",
        "deployment_failure": "Deployment failed on the provider.",
        "privacy_block": "Privacy policy blocked the operation.",
        "egress_block": "Egress policy blocked external calls.",
    }.get(category, "Failure cause is unclear from available logs.")
