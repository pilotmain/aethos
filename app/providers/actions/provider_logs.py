# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Classify provider CLI failures and summarize logs safely (Phase 2 Step 4)."""

from __future__ import annotations

import re
from typing import Any

from app.providers.provider_privacy import redact_cli_output

_FAILURE_ORDER: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    ("privacy_block", (re.compile(r"privacy|pii|redact", re.I),)),
    ("egress_block", (re.compile(r"egress|blocked|forbidden", re.I),)),
    ("missing_provider_auth", (re.compile(r"not authenticated|login|whoami|unauthorized|401", re.I),)),
    ("missing_provider_cli", (re.compile(r"command not found|enoent|no such file", re.I),)),
    ("missing_workspace", (re.compile(r"enoent.*package\.json|could not read package\.json|no such file", re.I),)),
    ("missing_project_root", (re.compile(r"not linked|link a project|no project", re.I),)),
    ("build_failure", (re.compile(r"build failed|error occurred|npm err|ERR!", re.I),)),
    ("deployment_failure", (re.compile(r"deployment failed|failed to deploy", re.I),)),
    ("rollback_failure", (re.compile(r"rollback failed", re.I),)),
)


def classify_cli_text(text: str) -> str:
    blob = redact_cli_output(text or "", max_out=8000)
    for label, patterns in _FAILURE_ORDER:
        if any(p.search(blob) for p in patterns):
            return label
    if "cli_timeout" in blob:
        return "missing_provider_cli"
    return "deployment_failure"


def summarize_cli_streams(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    max_lines: int = 24,
) -> dict[str, Any]:
    merged = redact_cli_output((stderr or "") + "\n" + (stdout or ""), max_out=12_000)
    lines = [ln.strip() for ln in merged.splitlines() if ln.strip()]
    tail = lines[-max_lines:]
    category = classify_cli_text(merged) if returncode != 0 else "ok"
    return {
        "returncode": returncode,
        "failure_category": category,
        "summary_lines": tail,
        "preview": "\n".join(tail[-8:]),
    }
