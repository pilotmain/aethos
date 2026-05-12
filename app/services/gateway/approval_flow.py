# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Natural-language job approval routes — invoked from NexaGateway only (Phase 37 ctx)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.gateway.approval_persistence import finalize_job_after_gateway_approval
from app.services.gateway.approval_resume import resume_after_approval
from app.services.gateway.context import GatewayContext
from app.services.logging.logger import get_logger

_log = get_logger("gateway.approval")

_JOB_SERVICE: Any = None


def _http_err_chat(he: HTTPException) -> dict[str, Any]:
    d = he.detail
    return {"mode": "chat", "text": str(d) if d else "Request failed.", "intent": "approval"}


def _job_service():
    global _JOB_SERVICE
    if _JOB_SERVICE is None:
        from app.services.agent_job_service import AgentJobService

        _JOB_SERVICE = AgentJobService()
    return _JOB_SERVICE


def _merge_resume(
    payload: dict[str, Any],
    db: Session,
    ctx: GatewayContext,
    job: Any,
    decision: str,
) -> dict[str, Any]:
    payload["approval_resume"] = resume_after_approval(db, ctx, job, decision)
    ctx.approval_state = {
        "job_id": getattr(job, "id", None),
        "status": getattr(job, "status", None),
        "decision": decision,
    }
    finalize_job_after_gateway_approval(db, job, ctx.user_id, decision)
    return payload


def try_gateway_approval_route(
    ctx: GatewayContext,
    text: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Match NL approval / dev-job decisions. Returns a gateway-shaped dict or None.

    Owner paths use ``ctx.permissions`` (``owner``, ``telegram_role``).
    """
    raw = (text or "").strip()
    if not raw:
        return None

    user_id = ctx.user_id
    channel = ctx.channel
    tstrip = raw
    tlow = tstrip.lower()

    tg_role = ctx.permissions.get("telegram_role")
    is_owner = bool(ctx.permissions.get("owner"))
    telegram_uid = ctx.extras.get("telegram_user_id")
    telegram_username = ctx.extras.get("telegram_username")
    chat_id = ctx.extras.get("telegram_chat_id")

    from app.services.telegram_access_audit import log_access_denied
    from app.services.user_capabilities import ACCESS_RESTRICTED, is_owner_role

    def _deny_gateway(*, family: str, reason: str, preview: str | None = None) -> dict[str, Any]:
        if telegram_uid is not None:
            try:
                log_access_denied(
                    db,
                    app_user_id=user_id,
                    telegram_id=int(telegram_uid),
                    username=telegram_username,
                    command_family=family,
                    reason=reason,
                    preview=preview,
                )
            except Exception:
                _log.warning("approval audit log failed", exc_info=True)
        return {"mode": "chat", "text": ACCESS_RESTRICTED, "intent": "access_denied"}

    if channel == "web":
        effective_owner = True
    else:
        effective_owner = is_owner or (tg_role is not None and is_owner_role(tg_role))

    if tlow == "approve despite failed tests":
        if not effective_owner:
            return _deny_gateway(family="approve", reason="not_owner", preview=None)
        js = _job_service()
        rows = js.list_jobs(db, user_id, limit=40)
        j_ov = next(
            (
                r
                for r in rows
                if (r.worker_type or "") == "dev_executor"
                and (r.status or "") == "failed"
                and (r.tests_status or "") == "failed"
            ),
            None,
        )
        if not j_ov:
            return {
                "mode": "chat",
                "text": (
                    "No `failed` dev job with failed tests found. List recent jobs first, or use this after the worker "
                    "reports a test failure."
                ),
                "intent": "approval",
            }
        o = js.mark_waiting_approval_despite_failed_tests(db, user_id, j_ov.id)
        if not o:
            return {
                "mode": "chat",
                "text": "Could not open approval for that job (check ownership).",
                "intent": "approval",
            }
        rtxt = (o.result or "")[:12_000]
        side: list[dict[str, Any]] = []
        if chat_id is not None:
            side.append(
                {
                    "kind": "telegram_send_approval_card",
                    "chat_id": str(chat_id),
                    "job_id": int(o.id),
                    "result_text": rtxt,
                }
            )
        base = {
            "mode": "chat",
            "text": (
                "Okay — I will allow approval despite failed tests. Review the branch and diff on the host before you tap Approve."
            ),
            "intent": "approval",
            "side_effects": side,
        }
        return _merge_resume(base, db, ctx, o, "override_failed_tests")

    mhr = re.match(r"^approve high risk job\s*#?(\d+)\s*$", tlow)
    if mhr:
        if not effective_owner:
            return _deny_gateway(family="job", reason="high_risk", preview=None)
        try:
            j = _job_service().approve_high_risk(db, user_id, int(mhr.group(1)))
        except HTTPException as he:
            return _http_err_chat(he)
        base = {
            "mode": "chat",
            "text": (
                f"Job #{j.id} is now `{j.status}`. Reply: `approve job #{j.id}` to run the dev worker."
            ),
            "intent": "approval",
        }
        return _merge_resume(base, db, ctx, j, "approve_high_risk")

    if channel == "telegram" and tlow in {"approve", "yes"} and tstrip.count(" ") == 0:
        if not effective_owner:
            return _deny_gateway(family="approve", reason="one_word_approve", preview=None)
        j_approve = _job_service().mark_autonomous_approved(db, user_id)
        if j_approve:
            base = {
                "mode": "chat",
                "text": (
                    f"Approved job #{j_approve.id} for commit. "
                    "The next `dev_agent_executor` run will commit on the feature branch (status: approved_to_commit)."
                ),
                "intent": "approval",
            }
            return _merge_resume(base, db, ctx, j_approve, "approve_autonomous")
        return None

    if channel == "telegram" and tlow == "reject" and tstrip.count(" ") == 0:
        if not effective_owner:
            return _deny_gateway(family="reject", reason="one_word", preview=None)
        j_rej = _job_service().mark_autonomous_rejected(db, user_id)
        if j_rej:
            base = {
                "mode": "chat",
                "text": (
                    f"Job #{j_rej.id} rejected. Working tree was reset to the pre-agent snapshot where possible. "
                    f"Status: {j_rej.status}."
                ),
                "intent": "approval",
            }
            return _merge_resume(base, db, ctx, j_rej, "reject_autonomous")
        return None

    approve_match = re.match(r"^(approve|deny)\s+job\s*#?(\d+)$", tlow)
    if approve_match:
        if not effective_owner:
            return _deny_gateway(family="approve", reason="job_line", preview=None)
        decision = "approve" if approve_match.group(1) == "approve" else "deny"
        job_id = int(approve_match.group(2))
        from app.services.ops_approval import process_ops_job_decision

        js = _job_service()
        a_ops = process_ops_job_decision(db, js, user_id, job_id, decision)
        if a_ops is not None:
            return {"mode": "chat", "text": a_ops, "intent": "approval"}
        try:
            job = js.decide(db, user_id, job_id, decision)
        except HTTPException as he:
            return _http_err_chat(he)
        if decision == "approve" and (getattr(job, "worker_type", None) or "") == "dev_executor":
            pl = dict(getattr(job, "payload_json", None) or {})
            ed = pl.get("execution_decision") or {}
            tool = ed.get("tool_key") or pl.get("preferred_dev_tool") or "—"
            mode = ed.get("mode") or pl.get("dev_execution_mode") or "—"
            pk = (pl.get("project_key") or "aethos") or "aethos"
            base = {
                "mode": "chat",
                "text": (
                    f"AethOS accepted dev task #{job.id}.\n\n"
                    f"Project: `{pk}`\n"
                    f"Tool: `{tool}`\n"
                    f"Mode: `{mode}`\n"
                    f"Status: scheduled for execution.\n"
                ),
                "intent": "approval",
            }
            return _merge_resume(base, db, ctx, job, decision)
        base = {"mode": "chat", "text": f"Job #{job.id} is now {job.status}.", "intent": "approval"}
        return _merge_resume(base, db, ctx, job, decision)

    approve_review_match = re.match(r"^approve\s+review\s+job\s*#?(\d+)$", tlow)
    if approve_review_match:
        if not effective_owner:
            return _deny_gateway(family="approve", reason="review", preview=None)
        try:
            job = _job_service().approve_review(db, user_id, int(approve_review_match.group(1)))
        except HTTPException as he:
            return _http_err_chat(he)
        base = {"mode": "chat", "text": f"Job #{job.id} is now {job.status}.", "intent": "approval"}
        return _merge_resume(base, db, ctx, job, "approve_review")

    approve_commit_match = re.match(r"^approve\s+commit\s+job\s*#?(\d+)$", tlow)
    if approve_commit_match:
        if not effective_owner:
            return _deny_gateway(family="approve", reason="commit", preview=None)
        try:
            job = _job_service().approve_commit(db, user_id, int(approve_commit_match.group(1)))
        except HTTPException as he:
            return _http_err_chat(he)
        base = {"mode": "chat", "text": f"Job #{job.id} is now {job.status}.", "intent": "approval"}
        return _merge_resume(base, db, ctx, job, "approve_commit")

    return None


__all__ = ["try_gateway_approval_route"]
