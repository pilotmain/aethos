# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Railway operator diagnostics — delegates to bounded Phase 58 runner."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.external_execution_access import assess_external_execution_access
from app.services.external_execution_runner import (
    format_investigation_for_chat,
    run_bounded_railway_repo_investigation,
)


def run_railway_operator_readonly(db: Session, user_id: str) -> tuple[str, dict[str, Any], list[str], bool]:
    """Same safe commands as ``external_execution_runner`` (whoami/status/logs/git status)."""
    access = assess_external_execution_access(db, user_id)
    collected: dict[str, object] = {
        "deploy_mode": "report_then_approve",
        "permission_to_probe": True,
        "auth_method": "token_env" if access.railway_token_present else "local_cli",
    }
    inv = run_bounded_railway_repo_investigation(db, user_id, collected)
    text = format_investigation_for_chat(inv)
    progress = list(inv.progress_lines) or ["Starting investigation", "Running bounded Railway checks"]
    evidence: dict[str, Any] = {
        "provider": "railway",
        "skipped_reason": inv.skipped_reason,
        "workspace_paths": inv.workspace_paths,
        "railway_whoami": inv.railway_whoami,
        "railway_status": inv.railway_status,
        "railway_logs": inv.railway_logs,
        "git_status": inv.git_status,
    }
    verified = inv.any_command_ok()
    return text, evidence, progress, verified
