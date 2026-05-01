"""Orchestrate dev missions — Phase 25 bounded test/fix loop."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevRun, NexaDevStep
from app.services.dev_runtime.coding_agents.base import CodingAgentRequest, CodingAgentResult
from app.services.dev_runtime.coding_agents.registry import choose_adapter
from app.services.dev_runtime.git_tools import (
    changed_files,
    create_commit,
    get_diff_summary,
    git_status,
)
from app.services.dev_runtime.git_tools import (
    prepare_pr_summary as ws_prepare_pr_summary,
)
from app.services.dev_runtime.github_pr import create_pull_request
from app.services.dev_runtime.planner import build_dev_plan
from app.services.dev_runtime.pr import is_pr_ready
from app.services.dev_runtime.privacy import (
    PrivacyBlockedError,
    gate_agent_context_before_external,
    redact_output_for_storage,
)
from app.services.dev_runtime.step_record import create_dev_step
from app.services.dev_runtime.tester import run_repo_tests
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


def _coding_result_to_dict(ca: CodingAgentResult) -> dict[str, Any]:
    return {
        "ok": ca.ok,
        "provider": ca.provider,
        "summary": redact_output_for_storage(ca.summary or ""),
        "error": redact_output_for_storage(ca.error or "") if ca.error else None,
        "changed_files": list(ca.changed_files or []),
        "commands_run": list(ca.commands_run or []),
        "test_result": ca.test_result,
    }


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
    max_iterations: int | None = None,
    schedule: dict[str, Any] | None = None,
    from_scheduler: bool = False,
) -> dict[str, Any]:
    _ = schedule
    if from_scheduler:
        allow_commit = False
        allow_push = False

    ws = get_workspace(db, user_id, workspace_id)
    if ws is None:
        raise ValueError("workspace_not_found")

    if max_iterations is not None:
        mi = int(max_iterations)
        if mi < 1 or mi > 20:
            raise ValueError("max_iterations out of range (1–20)")
        max_loop_iters = mi
    else:
        max_loop_iters = 3

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
    mission_goal = (goal or "").strip()
    current_goal = mission_goal
    loop_iterations_executed = 0
    tests_passed = False
    has_runtime_errors = False

    try:
        run.status = "running"
        run.started_at = _utc_now()
        plan = build_dev_plan(goal, ws)
        run.plan_json = plan
        db.commit()

        for step in plan:
            stype = str(step.get("type") or "")
            if stype == "summary":
                continue

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

        # Phase 25 — bounded adapter / test loop
        iteration = 0
        while iteration < max_loop_iters:
            iteration += 1
            loop_iterations_executed = iteration

            adapter_impl = choose_adapter(preferred_agent)
            adapter_used_name = adapter_impl.name

            diff_payload = get_diff_summary(repo)
            ctx_clean: dict[str, Any] = {
                "steps_so_far": context_accum,
                "diff": diff_payload,
                "original_goal": mission_goal,
                "failures": context_accum.get("failures"),
                "last_test_failures": context_accum.get("last_test_failures"),
            }
            ctx_clean = dict(
                gate_agent_context_before_external(
                    adapter_impl.name,
                    ctx_clean,
                    db=db,
                    user_id=user_id,
                )
            )

            input_snapshot = {
                "goal": current_goal,
                "diff": {
                    "changed_files": diff_payload.get("changed_files", [])[:80],
                    "changed_file_count": diff_payload.get("changed_file_count", 0),
                    "diff_chars": diff_payload.get("diff_chars", 0),
                    "has_uncommitted": diff_payload.get("has_uncommitted", False),
                },
                "iteration": iteration,
            }

            req = CodingAgentRequest(
                user_id=user_id,
                run_id=rid,
                workspace_id=workspace_id,
                repo_path=str(repo),
                goal=current_goal,
                context=ctx_clean,
                max_iterations=3,
                allow_write=allow_write,
                allow_commit=allow_commit,
                allow_push=allow_push,
                cost_budget_usd=float(cost_budget_usd or 0.0),
            )

            ca = adapter_impl.run(req)
            adapter_used_name = ca.provider
            out_dict = _coding_result_to_dict(ca)

            cmd_line = (ca.commands_run[0] if ca.commands_run else None) or f"adapter:{ca.provider}"
            row_loop = create_dev_step(
                db,
                run_id=rid,
                step_type="loop_iteration",
                iteration=iteration,
                adapter=ca.provider,
                input_json=input_snapshot,
                output_json=out_dict,
                command=cmd_line,
                output_text=json.dumps(out_dict, ensure_ascii=False, default=str)[:100_000],
                artifact_json=out_dict,
            )
            row_loop.output = redact_output_for_storage(row_loop.output or "")
            row_loop.status = "completed"
            row_loop.completed_at = _utc_now()

            test_bundle = run_repo_tests(repo)
            row_loop.test_result = test_bundle
            db.commit()

            step_blob = {
                "id": row_loop.id,
                "type": "loop_iteration",
                "iteration": iteration,
                "adapter": ca.provider,
                "command": cmd_line,
                "output_preview": (row_loop.output or "")[:2000],
                "status": row_loop.status,
                "tests_ok": test_bundle.get("ok"),
            }
            steps_out.append(step_blob)
            context_accum[f"loop_iteration_{iteration}"] = {"agent": out_dict, "tests": test_bundle}

            emit_runtime_event(
                "dev.loop.iteration",
                user_id=user_id,
                payload={
                    "run_id": rid,
                    "iteration": iteration,
                    "adapter": ca.provider,
                    "tests_ok": test_bundle.get("ok"),
                    "step_id": row_loop.id,
                },
            )
            emit_runtime_event(
                "dev.step.completed",
                user_id=user_id,
                payload={"run_id": rid, "step_type": "loop_iteration", "step_id": row_loop.id},
            )

            if not ca.ok:
                has_runtime_errors = True
                break

            if test_bundle.get("ok"):
                tests_passed = True
                break

            parsed = test_bundle.get("parsed") or {}
            context_accum["failures"] = parsed
            context_accum["last_test_failures"] = test_bundle.get("summary")
            current_goal = f"Fix failing tests: {test_bundle.get('summary', '')[:1200]}"

        if not tests_passed and not has_runtime_errors and loop_iterations_executed >= max_loop_iters:
            pass  # exhausted without pass

        cf_end = changed_files(repo)
        commit_result: dict[str, Any] | None = None
        if allow_commit:
            commit_result = create_commit(
                repo,
                f"nexa dev: {mission_goal[:120]}",
                allow_commit=True,
            )

        push_result: dict[str, Any] | None = None
        if allow_push:
            push_result = {"ok": False, "error": "push_not_implemented_use_manual_git_push"}

        # Summary step (plan)
        for step in plan:
            if str(step.get("type") or "") != "summary":
                continue
            row = NexaDevStep(
                run_id=rid,
                step_type="summary",
                status="running",
                command=None,
                output=None,
                artifact_json=None,
                created_at=_utc_now(),
            )
            db.add(row)
            db.flush()

            run_blob: dict[str, Any] = {
                "goal": mission_goal,
                "steps": steps_out,
                "adapter_used": adapter_used_name,
                "preferred_agent": preferred_agent,
                "allow_write": allow_write,
                "allow_commit": allow_commit,
                "allow_push": allow_push,
                "iterations": loop_iterations_executed,
                "tests_passed": tests_passed,
                "has_runtime_errors": has_runtime_errors,
                "max_iterations": max_loop_iters,
            }
            pr_ui = ws_prepare_pr_summary(ws, run_blob)
            gh = create_pull_request(goal=mission_goal, run_result=run_blob, workspace_id=workspace_id)
            if auto_pr:
                pr_ui["auto_pr_requested"] = True
                pr_ui["github_pr_stub"] = gh
            pr_ui["pr_ready"] = is_pr_ready(
                {
                    **run_blob,
                    "changed_files_end": cf_end,
                    "status": "completed",
                }
            )
            out_text = json.dumps(pr_ui, ensure_ascii=False)[:50_000]
            row.output = redact_output_for_storage(out_text)
            row.artifact_json = pr_ui
            row.status = "completed"
            row.completed_at = _utc_now()
            db.commit()

            steps_out.append(
                {
                    "id": row.id,
                    "type": "summary",
                    "command": None,
                    "output_preview": (row.output or "")[:2000],
                    "status": row.status,
                }
            )

            emit_runtime_event(
                "dev.step.completed",
                user_id=user_id,
                payload={"run_id": rid, "step_type": "summary", "step_id": row.id},
            )

        result_payload: dict[str, Any] = {
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
            "iterations": loop_iterations_executed,
            "tests_passed": tests_passed,
            "has_runtime_errors": has_runtime_errors,
            "max_iterations": max_loop_iters,
        }
        result_payload["pr_ready"] = is_pr_ready({**result_payload, "status": "completed"})

        run.result_json = result_payload
        run.status = "completed"
        run.completed_at = _utc_now()
        run.error = None
        db.commit()

        emit_runtime_event(
            "dev.run.completed",
            user_id=user_id,
            payload={
                "run_id": rid,
                "status": "completed",
                "iterations": loop_iterations_executed,
                "tests_passed": tests_passed,
            },
        )
        update_state([])

        return {
            "ok": True,
            "run_id": rid,
            "status": run.status,
            "steps": steps_out,
            "adapter_used": adapter_used_name,
            "iterations": loop_iterations_executed,
            "tests_passed": tests_passed,
            "pr_ready": result_payload["pr_ready"],
            "has_runtime_errors": has_runtime_errors,
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
        return {
            "ok": False,
            "run_id": rid,
            "status": "blocked",
            "error": str(exc),
            "steps": steps_out,
            "iterations": loop_iterations_executed,
            "tests_passed": False,
            "pr_ready": False,
            "has_runtime_errors": False,
        }

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
        return {
            "ok": False,
            "run_id": rid,
            "status": "failed",
            "error": str(exc),
            "steps": steps_out,
            "iterations": loop_iterations_executed,
            "tests_passed": False,
            "pr_ready": False,
            "has_runtime_errors": True,
        }


__all__ = ["run_dev_mission"]
