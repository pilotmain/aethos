# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Nexa Ops: approval-gated jobs (worker_type=ops_worker) and on-approve execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.services.ops_actions import OPS_ACTIONS, OpsAction
from app.services.ops_executor import execute_action

if TYPE_CHECKING:
    from app.models.agent_job import AgentJob
    from app.services.agent_job_service import AgentJobService

WORKER_TYPE = "ops_worker"
KIND = "ops_action"


def is_ops_action_job(job: "AgentJob | None") -> bool:
    if not job:
        return False
    return (getattr(job, "worker_type", None) or "") == WORKER_TYPE and (
        getattr(job, "kind", None) or ""
    ) == KIND


def build_ops_approval_message(
    action: OpsAction, job_id: int, *, project_block: str | None = None
) -> str:
    extra = f"\n{project_block}\n" if (project_block or "").strip() else ""
    return (
        f"⚠️ **AethOS Ops** — this action needs approval (job `#{job_id}`):\n\n"
        f"**{action.name}** — {action.description}\n"
        f"{extra}\n"
        f"Reply: `approve job #{job_id}`  or  `deny job #{job_id}`"
    )


def process_ops_job_decision(
    db: Session,
    job_service: "AgentJobService",
    user_id: str,
    job_id: int,
    decision: str,
) -> str | None:
    """
    If job is a Nexa ops action, handle approve/deny and return a message.
    Return None to fall back to the generic `decide` path.
    """
    from app.models.agent_job import AgentJob  # noqa: F401

    job = job_service.repo.get(db, job_id, user_id)
    if not job or not is_ops_action_job(job):
        return None
    st = (job.status or "")
    if st in ("completed", "failed", "cancelled", "rejected", "blocked"):
        return None
    if st != "needs_approval":
        return None
    if decision not in ("approve", "deny"):
        return None
    if decision == "deny":
        j = job_service.decide(db, user_id, job_id, "deny")
        return f"Job #{j.id} is now {j.status}."
    pl = dict(job.payload_json or {})
    name = (pl.get("ops_action") or "").strip()
    if not name or name not in OPS_ACTIONS:
        j = job_service.mark_failed(
            db,
            job,
            "Invalid or missing ops_action in job payload for AethOS.",
            result="AethOS could not read this job's ops action.",
        )
        return f"Job #{j.id} failed: invalid payload."
    try:
        payload = pl.get("ops_payload") or {}
        out = execute_action(
            name,
            payload,
            db=db,
            app_user_id=user_id,
        )[:10_000]  # active project comes from payload ops_payload
    except Exception as exc:  # noqa: BLE001
        j = job_service.mark_failed(
            db,
            job,
            str(exc)[:2000] or "Execution error",
        )
        return "Something went wrong while executing this action. Check logs or try again in AethOS."
    j2 = job_service.mark_completed(
        db,
        job,
        f"AethOS Ops (approved)\n\n{out}"[:10_000],
    )
    return f"**AethOS Ops** — job #{j2.id} done.\n\n{out[:3500]}" + (
        "…" if len(out) > 3500 else ""
    )
