"""Orchestrate dev missions (inspect → test → agent → test → summary)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevRun, NexaDevStep, NexaDevWorkspace
from app.services.dev_runtime.coding_agents.local_stub import LocalStubCodingAgent
from app.services.dev_runtime.git_tools import git_status
from app.services.dev_runtime.planner import build_dev_plan
from app.services.dev_runtime.pr import prepare_pr_summary
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
) -> dict[str, Any]:
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

    try:
        run.status = "running"
        run.started_at = _utc_now()
        plan = build_dev_plan(goal, ws)
        run.plan_json = plan
        db.commit()

        agent = LocalStubCodingAgent()

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
                artifact = {"git_status": gs}
            elif stype == "test":
                cmd_ran = pick_test_command(repo)
                row.command = cmd_ran
                te = run_dev_command(repo, cmd_ran)
                out_text = _format_cmd_result(te)
                artifact = {"command_result": te}
            elif stype == "edit":
                artifact = agent.run(ws, goal, {"steps_so_far": context_accum})
                out_text = json.dumps(artifact, ensure_ascii=False, default=str)[:100_000]
            elif stype == "summary":
                pr = prepare_pr_summary(goal, {"steps": steps_out})
                if auto_pr:
                    pr["auto_pr_requested"] = True
                artifact = pr
                out_text = json.dumps(pr, ensure_ascii=False)[:50_000]
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

        run.result_json = {
            "steps": steps_out,
            "workspace_id": workspace_id,
            "repo_path": str(repo),
            "auto_pr": auto_pr,
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
