# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Fix-and-redeploy orchestration (Phase 2 Step 6)."""

from __future__ import annotations

import os
from typing import Any

from app.core.config import get_settings
from app.deploy_context.context_execution import execute_vercel_logs, execute_vercel_redeploy
from app.deploy_context.context_history import record_operator_provider_action
from app.deploy_context.context_resolution import build_deploy_context
from app.deploy_context.errors import OperatorDeployError
from app.providers.repair.failure_classification import diagnose_failure
from app.providers.repair.repair_context import create_repair_context, update_repair_context
from app.providers.repair.repair_execution import execute_repair_plan
from app.providers.repair.repair_planner import build_repair_plan
from app.rendering.repair_summary import render_fix_and_redeploy_blocked, render_fix_and_redeploy_success


def _privacy_allows(text: str) -> tuple[bool, str | None]:
    try:
        from app.privacy.egress_guard import evaluate_egress
        from app.privacy.pii_detection import detect_pii

        s = get_settings()
        cats = [m.category for m in detect_pii(text or "")]
        ok, reason = evaluate_egress(s, "provider_repair", pii_categories=cats)
        if not ok:
            return False, reason
    except Exception:
        return True, None
    return True, None


def run_fix_and_redeploy(
    project_id: str,
    *,
    environment: str = "production",
    source: str = "gateway_nl",
    raw_text: str = "",
) -> dict[str, Any]:
    """
    End-to-end fix-and-redeploy workflow.

    Returns ``{success, summary, repair_context, plan, execution, deploy_result}``.
    """
    allowed, reason = _privacy_allows(raw_text or project_id)
    if not allowed:
        mode = (get_settings().aethos_privacy_mode or "").strip().lower()
        cat = "egress_block" if mode == "block" else "privacy_block"
        return {
            "success": False,
            "summary": f"Blocked by privacy policy ({cat}).",
            "blocked_reason": cat,
        }

    deploy_ctx = build_deploy_context(project_id, provider="vercel", environment=environment)

    logs_result = execute_vercel_logs(project_id, environment=environment, limit=60)
    logs_preview = str(logs_result.get("summary") or "")
    extra = logs_result.get("extra") or {}
    if isinstance(extra, dict):
        cli = extra.get("cli") or {}
        if isinstance(cli, dict) and cli.get("preview"):
            logs_preview = str(cli.get("preview"))

    diagnosis = diagnose_failure(
        logs_preview=logs_preview,
        workspace_signals=list(deploy_ctx.get("confidence_signals") or []),
    )

    repair_ctx = create_repair_context(
        project_id=project_id,
        deploy_ctx=deploy_ctx,
        diagnosis=diagnosis,
        logs_summary=logs_preview,
        source=source,
    )

    if diagnosis.get("needs_provider_login"):
        update_repair_context(
            project_id,
            str(repair_ctx["repair_context_id"]),
            {"status": "blocked", "blocked_reason": "missing_provider_auth"},
        )
        record_operator_provider_action(
            {
                "source": source,
                "intent": "fix_and_redeploy",
                "project_id": project_id,
                "provider": "vercel",
                "success": False,
                "summary": "missing_provider_auth",
            }
        )
        return {
            "success": False,
            "summary": render_fix_and_redeploy_blocked(
                project_id=project_id,
                repo_path=str(deploy_ctx.get("repo_path") or ""),
                reason="Vercel CLI is not authenticated.",
                diagnosis=diagnosis,
                next_hint="Run: vercel login\nThen: aethos providers scan",
            ),
            "repair_context": repair_ctx,
        }

    plan = build_repair_plan(repair_context=repair_ctx, deploy_ctx=deploy_ctx)
    execution = execute_repair_plan(plan, deploy_ctx=deploy_ctx)

    actions_taken = []
    for row in execution.get("actions") or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") == "shell" and row.get("command"):
            actions_taken.append(f"Ran `{row['command']}`")
        elif row.get("type") == "verify" and row.get("command"):
            actions_taken.append(f"Verified with `{row['command']}`")
        elif row.get("type") == "inspect":
            actions_taken.append(f"Inspected `{row.get('target')}`")

    if not execution.get("ok"):
        blocked = str(execution.get("blocked_reason") or "verification_failed")
        update_repair_context(
            project_id,
            str(repair_ctx["repair_context_id"]),
            {
                "status": "blocked",
                "blocked_reason": blocked,
                "plan_id": plan.get("plan_id"),
                "execution": execution,
            },
        )
        record_operator_provider_action(
            {
                "source": source,
                "intent": "fix_and_redeploy",
                "project_id": project_id,
                "provider": "vercel",
                "success": False,
                "summary": blocked,
            }
        )
        fail_cmd = execution.get("failed_command")
        reason = "Local verification failed."
        if fail_cmd:
            reason += f" Command `{fail_cmd}` exited non-zero."
        return {
            "success": False,
            "summary": render_fix_and_redeploy_blocked(
                project_id=project_id,
                repo_path=str(deploy_ctx.get("repo_path") or ""),
                reason=reason,
                diagnosis=diagnosis,
                verification=execution.get("verification"),
            ),
            "repair_context": repair_ctx,
            "plan": plan,
            "execution": execution,
        }

    deploy_result = execute_vercel_redeploy(project_id, environment=environment)
    ok = bool(deploy_result.get("success"))

    update_repair_context(
        project_id,
        str(repair_ctx["repair_context_id"]),
        {
            "status": "completed" if ok else "deploy_failed",
            "plan_id": plan.get("plan_id"),
            "execution": execution,
            "deploy_result": deploy_result,
        },
    )

    record_operator_provider_action(
        {
            "source": source,
            "intent": "fix_and_redeploy",
            "project_id": project_id,
            "provider": "vercel",
            "success": ok,
            "summary": str(deploy_result.get("summary") or ""),
            "deployment_id": deploy_result.get("deployment_id"),
            "url": deploy_result.get("url"),
        }
    )

    repo_path = str(deploy_ctx.get("repo_path") or "")
    if ok:
        if not actions_taken:
            actions_taken.append("Completed workspace verification")
        actions_taken.append("Redeployed to Vercel production")
        summary = render_fix_and_redeploy_success(
            project_id=project_id,
            repo_path=repo_path,
            diagnosis=diagnosis,
            actions_taken=actions_taken,
            deploy_result=deploy_result,
        )
    else:
        summary = render_fix_and_redeploy_blocked(
            project_id=project_id,
            repo_path=repo_path,
            reason="Verification passed but provider redeploy failed.",
            diagnosis=diagnosis,
            next_hint=f"Check provider logs, then:\nredeploy {project_id}",
        )

    return {
        "success": ok,
        "summary": summary,
        "repair_context": repair_ctx,
        "plan": plan,
        "execution": execution,
        "deploy_result": deploy_result,
    }
