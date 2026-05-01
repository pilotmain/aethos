"""Orchestrate dev missions (inspect → test → agent → test → summary)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevRun, NexaDevStep, NexaDevWorkspace
from app.services.dev_runtime.coding_agents.base import CodingAgentRequest
from app.services.dev_runtime.coding_agents.registry import choose_adapter
from app.services.dev_runtime.git_tools import (
    changed_files,
    create_commit,
    git_status,
    prepare_pr_summary as ws_prepare_pr_summary,
)
from app.services.dev_runtime.github_pr import create_pull_request
from app.services.dev_runtime.planner import build_dev_plan
from app.services.dev_runtime.privacy import PrivacyBlockedError, redact_output_for_storage
from app.services.dev_runtime.executor import run_dev_command
from app.services.dev_runtime.tester import pick_test_command
from app.services.dev_runtime.workspace import get_workspace
from app.services.events.envelope import emit_runtime_event
from app.services.mission_control.nexa_next_state import update_state


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_cmd_result(r: dict[str, Any]) -> str:
    parts = []
    if r.get("stdout"):
        parts.append(str(r["stdout"]))
    if r.get("stderr"):
        parts.append("--- stderr ---\n" + str(r["stderr"]))
    if r.get("error"):
        parts.append("error: " + str(r["error"]))
    return "\n".join(parts).strip()


def run_dev_mission(
    db: Session,
    user_id: str,
    workspace_id: str,
    goal: str,
    *,
    auto_pr: bool = False,
    preferred_agent: str | None = None,
    allow_write: bool = False,
    allow_commit: bool = False,
    allow_push: bool = False,
    cost_budget_usd: float = 0.0,
    schedule: dict[str, Any] | None = None,
    from_scheduler: bool = False,
) -> dict[str, Any]:
    _ = schedule  # scheduling is handled at the HTTP layer
    if from_scheduler:
        allow_commit = False
        allow_push = False

    ws = get_workspace(db, user_id, workspace_id)
    if ws is None:
        raise ValueError("workspace_not_found")

    rid = str(uuid.uuid4())
    run = NexaDevRun(
        id=rid,
        user_id=user_id,
        workspace_id=workspace_id,
        mission_id=None,
        goal=(goal or "").strip()[:50_000],
        status="queued",
        plan_json=None,
        result_json=None,
        created_at=_utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    emit_runtime_event(
        "dev.run.created",
        user_id=user_id,
        payload={"run_id": rid, "workspace_id": workspace_id, "goal": goal[:500]},
    )

    repo = Path(ws.repo_path)
    steps_out: list[dict[str, Any]] = []
    context_accum: dict[str, Any] = {}
    adapter_used_name = "local_stub"

    try:
        run.status = "running"
        run.started_at = _utc_now()
        plan = build_dev_plan(goal, ws)
        run.plan_json = plan
        db.commit()

        adapter_impl = choose_adapter(preferred_agent)

        for step in plan:
            stype = str(step.get("type") or "")
            row = NexaDevStep(
                run_id=rid,
                step_type=stype,
                status="running",
                command=None,
                output=None,
                artifact_json=None,
                created_at=_utc_now(),
            )
            db.add(row)
            db.flush()

            out_text = ""
            cmd_ran: str | None = None
            artifact: dict[str, Any] | None = None

            if stype == "inspect":
                gs = git_status(repo)
                cmd_ran = "git status"
                row.command = cmd_ran
                out_text = _format_cmd_result(gs)
                artifact = {"git_status": gs, "changed_files": changed_files(repo)}
            elif stype == "test":
                cmd_ran = pick_test_command(repo)
                row.command = cmd_ran
                te = run_dev_command(repo, cmd_ran)
                out_text = _format_cmd_result(te)
                artifact = {"command_result": te}
            elif stype == "edit":
                req = CodingAgentRequest(
                    user_id=user_id,
                    run_id=rid,
                    workspace_id=workspace_id,
                    repo_path=str(repo),
                    goal=goal,
                    context={"steps_so_far": context_accum},
                    max_iterations=3,
                    allow_write=allow_write,
                    allow_commit=allow_commit,
                    allow_push=allow_push,
                    cost_budget_usd=float(cost_budget_usd or 0.0),
                )
                ca = adapter_impl.run(req)
                adapter_used_name = ca.provider
                summary_safe = redact_output_for_storage(ca.summary or "")
                err_safe = redact_output_for_storage(ca.error or "") if ca.error else None
                artifact = {
                    "ok": ca.ok,
                    "adapter": ca.provider,
                    "summary": summary_safe,
                    "changed_files": list(ca.changed_files or []),
                    "commands_run": list(ca.commands_run or []),
                    "test_result": ca.test_result,
                    "error": err_safe,
                }
                cmd_ran = (ca.commands_run[0] if ca.commands_run else None) or f"adapter:{ca.provider}"
                row.command = cmd_ran
                out_text = json.dumps(artifact, ensure_ascii=False, default=str)[:100_000]
            elif stype == "summary":
                run_blob: dict[str, Any] = {
                    "goal": goal,
                    "steps": steps_out,
                    "adapter_used": adapter_used_name,
                    "preferred_agent": preferred_agent,
                    "allow_write": allow_write,
                    "allow_commit": allow_commit,
                    "allow_push": allow_push,
                }
                pr_ui = ws_prepare_pr_summary(ws, run_blob)
                gh = create_pull_request(goal=goal, run_result=run_blob, workspace_id=workspace_id)
                if auto_pr:
                    pr_ui["auto_pr_requested"] = True
                    pr_ui["github_pr_stub"] = gh
                artifact = pr_ui
                out_text = json.dumps(pr_ui, ensure_ascii=False)[:50_000]
            else:
                out_text = "unknown_step_type"

            row.output = redact_output_for_storage(out_text)
            row.artifact_json = artifact
            row.status = "completed"
            row.completed_at = _utc_now()
            db.commit()

            step_blob = {
                "id": row.id,
                "type": stype,
                "command": cmd_ran,
                "output_preview": (row.output or "")[:2000],
                "status": row.status,
            }
            steps_out.append(step_blob)
            context_accum[stype] = artifact

            emit_runtime_event(
                "dev.step.completed",
                user_id=user_id,
                payload={"run_id": rid, "step_type": stype, "step_id": row.id},
            )

        cf_end = changed_files(repo)
        commit_result: dict[str, Any] | None = None
        if allow_commit:
            commit_result = create_commit(
                repo,
                f"nexa dev: {(goal or '').strip()[:120]}",
                allow_commit=True,
            )

        push_result: dict[str, Any] | None = None
        if allow_push:
            push_result = {
                "ok": False,
                "error": "push_not_implemented_use_manual_git_push",
            }

        run.result_json = {
            "steps": steps_out,
            "workspace_id": workspace_id,
            "repo_path": str(repo),
            "auto_pr": auto_pr,
            "preferred_agent": (preferred_agent or "").strip() or None,
            "adapter_used": adapter_used_name,
            "allow_write": allow_write,
            "allow_commit": allow_commit,
            "allow_push": allow_push,
            "cost_budget_usd": float(cost_budget_usd or 0.0),
            "changed_files_end": cf_end,
            "commit_result": commit_result,
            "push_result": push_result,
        }
        run.status = "completed"
        run.completed_at = _utc_now()
        run.error = None
        db.commit()

        emit_runtime_event(
            "dev.run.completed",
            user_id=user_id,
            payload={"run_id": rid, "status": "completed"},
        )
        update_state([])

        return {
            "ok": True,
            "run_id": rid,
            "status": run.status,
            "steps": steps_out,
            "adapter_used": adapter_used_name,
        }

    except PrivacyBlockedError as exc:
        run.status = "blocked"
        run.error = str(exc)
        run.completed_at = _utc_now()
        db.commit()
        emit_runtime_event(
            "dev.run.failed",
            user_id=user_id,
            payload={"run_id": rid, "status": "blocked", "error": str(exc)},
        )
        update_state([])
        return {"ok": False, "run_id": rid, "status": "blocked", "error": str(exc), "steps": steps_out}

    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)[:20_000]
        run.completed_at = _utc_now()
        db.commit()
        emit_runtime_event(
            "dev.run.failed",
            user_id=user_id,
            payload={"run_id": rid, "status": "failed", "error": str(exc)},
        )
        update_state([])
        return {"ok": False, "run_id": rid, "status": "failed", "error": str(exc), "steps": steps_out}


__all__ = ["run_dev_mission"]
