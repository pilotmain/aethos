"""Orchestrate dev missions — Phase 25 bounded test/fix loop."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevRun, NexaDevStep
from app.services.dev_runtime.coding_agents.base import CodingAgentRequest, CodingAgentResult
from app.services.dev_runtime.coding_agents.registry import choose_adapter
from app.services.dev_runtime.git_tools import (
    changed_files,
    checkout_run_branch,
    commit_quality_preflight,
    create_commit,
    get_diff_summary,
    git_status,
    repo_sanity_check,
    rev_parse_head,
    rollback_last_commit,
    validate_commit,
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
from app.services.dev_runtime.failure_intel import (
    adaptive_next_goal,
    classify_dev_failure,
    detect_stagnation_signal,
    refine_dev_failure_detail,
    select_fix_strategy,
    select_fix_strategy_detail,
)
from app.services.dev_runtime.workspace import get_workspace
from app.services.events.envelope import emit_runtime_event
from app.core.config import get_settings
from app.services.memory.memory_index import MemoryIndex
from app.services.mission_control.nexa_next_state import update_state

# Phase 41–46 — documented pipeline surface (→ PR when GitHub enabled)
DEV_PIPELINE_SEQUENCE: tuple[str, ...] = (
    "analyze",
    "code",
    "test",
    "fix",
    "repeat",
    "commit",
    "pr",
)


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


def _merge_dev_memory_notes(user_id: str, goal: str, memory_notes: str | None) -> str | None:
    """Blend caller notes with semantic memory hits for dev planning (Phase 55)."""
    base = (memory_notes or "").strip()
    if not get_settings().nexa_memory_layer_enabled:
        return base[:4000] if base else None
    q = (goal or "").strip()[:2000]
    if not q:
        return base[:4000] if base else None
    hits = MemoryIndex().semantic_search(user_id, q, limit=8)
    if not hits:
        return base[:4000] if base else None
    lines: list[str] = []
    for e in hits:
        title = str(e.get("title") or "").strip()
        prev = str(e.get("preview") or "").strip()[:500]
        blob = f"- {title}\n{prev}".strip() if title or prev else ""
        if blob:
            lines.append(blob)
    if not lines:
        return base[:4000] if base else None
    chunk = "\n\n".join(lines)[:3000]
    if base:
        return (base + "\n\n[Memory recall]\n" + chunk)[:4000]
    return ("[Memory recall]\n" + chunk)[:4000]


def run_dev_mission(
    db: Session,
    user_id: str,
    workspace_id: str,
    goal: str,
    *,
    memory_notes: str | None = None,
    auto_pr: bool = False,
    preferred_agent: str | None = None,
    allow_write: bool = False,
    allow_commit: bool = False,
    allow_push: bool = False,
    cost_budget_usd: float = 0.0,
    max_iterations: int | None = None,
    schedule: dict[str, Any] | None = None,
    from_scheduler: bool = False,
    on_progress: Callable[[str], None] | None = None,
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
    run_branch_name = f"nexa/run-{rid[:16]}"
    if not from_scheduler:
        br = checkout_run_branch(repo, run_branch_name)
        context_accum: dict[str, Any] = {"run_branch": run_branch_name, "branch_checkout": br}
    else:
        context_accum = {"run_branch": None, "branch_checkout": {"ok": True, "skipped": True}}
    steps_out: list[dict[str, Any]] = []
    progress_messages: list[str] = []

    def _notify_progress(msg: str) -> None:
        m = (msg or "").strip()
        if not m:
            return
        progress_messages.append(m)
        if on_progress is not None:
            try:
                on_progress(m)
            except Exception:
                pass

    adapter_used_name = "local_stub"
    mission_goal = (goal or "").strip()
    current_goal = mission_goal
    loop_iterations_executed = 0
    tests_passed = False
    has_runtime_errors = False
    stagnation_count = 0
    last_failure_sig: str | None = None
    stagnation_stop = False

    try:
        run.status = "running"
        run.started_at = _utc_now()
        san = repo_sanity_check(repo)
        if not san.get("ok"):
            raise RuntimeError(f"repo_sanity_failed:{san.get('error')}")
        mem_trim = _merge_dev_memory_notes(user_id, mission_goal, memory_notes)
        plan = build_dev_plan(goal, ws, memory_notes=mem_trim)
        run.plan_json = plan
        db.commit()

        _notify_progress("Starting dev mission on your workspace…")

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

            if stype in ("inspect", "analyze"):
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
                "pipeline_phase": "analyze" if stype in ("analyze", "inspect") else stype,
            }
            steps_out.append(step_blob)
            context_accum[stype] = artifact

            step_label = (
                "Analyzing repository (git status)…"
                if stype in ("inspect", "analyze")
                else f"Step {stype}…"
            )
            _notify_progress(step_label)
            emit_runtime_event(
                "dev.step.completed",
                user_id=user_id,
                payload={
                    "run_id": rid,
                    "step_type": stype,
                    "step_id": row.id,
                    "progress_label": step_label,
                },
            )

        # Phase 42 — bounded retry: coding step → tests → failure-driven goal pivot until pass,
        # exhaustion (max_iterations), or adapter error (same bounds as Phase 25).
        iteration = 0
        while iteration < max_loop_iters:
            iteration += 1
            loop_iterations_executed = iteration

            _notify_progress(f"Running tests / fix iteration {iteration} of {max_loop_iters}…")

            adapter_impl = choose_adapter(
                preferred_agent,
                user_id=user_id,
                task_goal=current_goal,
            )
            adapter_used_name = adapter_impl.name

            diff_payload = get_diff_summary(repo)
            ctx_clean: dict[str, Any] = {
                "steps_so_far": context_accum,
                "diff": diff_payload,
                "original_goal": mission_goal,
                "failures": context_accum.get("failures"),
                "last_test_failures": context_accum.get("last_test_failures"),
            }
            if mem_trim:
                ctx_clean["user_memory_notes"] = mem_trim
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

            tests_ok = bool(test_bundle.get("ok"))
            try:
                from app.services.agents.agent_intel_store import record_agent_outcome

                record_agent_outcome(
                    user_id,
                    adapter_used_name,
                    success=bool(ca.ok and tests_ok),
                    meta={"run_id": rid, "iteration": iteration},
                )
            except Exception:
                pass
            pivot_next = not tests_ok and iteration < max_loop_iters
            step_blob = {
                "id": row_loop.id,
                "type": "loop_iteration",
                "iteration": iteration,
                "adapter": ca.provider,
                "command": cmd_line,
                "output_preview": (row_loop.output or "")[:2000],
                "status": row_loop.status,
                "tests_ok": test_bundle.get("ok"),
                "pipeline": {
                    "sequence": list(DEV_PIPELINE_SEQUENCE),
                    "code": {"adapter": ca.provider, "ok": ca.ok},
                    "test": {"ok": tests_ok, "summary": (test_bundle.get("summary") or "")[:500]},
                    "fix": {"next_iteration_planned": pivot_next},
                    "repeat": {"iteration": iteration, "max": max_loop_iters},
                },
            }
            steps_out.append(step_blob)
            context_accum[f"loop_iteration_{iteration}"] = {"agent": out_dict, "tests": test_bundle}

            loop_label = (
                "Tests passed."
                if tests_ok
                else "Tests still failing — applying another fix pass…"
            )
            _notify_progress(loop_label)
            emit_runtime_event(
                "dev.loop.iteration",
                user_id=user_id,
                payload={
                    "run_id": rid,
                    "iteration": iteration,
                    "adapter": ca.provider,
                    "tests_ok": test_bundle.get("ok"),
                    "step_id": row_loop.id,
                    "progress_label": loop_label,
                },
            )
            emit_runtime_event(
                "dev.step.completed",
                user_id=user_id,
                payload={
                    "run_id": rid,
                    "step_type": "loop_iteration",
                    "step_id": row_loop.id,
                    "progress_label": loop_label,
                },
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
            sig = str(test_bundle.get("summary") or "")[:2000]
            abort, stagnation_count, last_failure_sig = detect_stagnation_signal(
                sig, last_failure_sig, stagnation_count
            )
            if abort:
                stagnation_stop = True
                has_runtime_errors = True
                break
            detail = refine_dev_failure_detail(test_bundle.get("summary"), None)
            context_accum["last_fix_strategy"] = select_fix_strategy_detail(detail)
            current_goal = adaptive_next_goal(
                mission_goal,
                current_goal,
                detail,
                sig,
                memory_notes=mem_trim,
            )

        if not tests_passed and not has_runtime_errors and loop_iterations_executed >= max_loop_iters:
            pass  # exhausted without pass

        cf_end = changed_files(repo)
        commit_result: dict[str, Any] | None = None
        commit_hash: str | None = None
        commit_quality: dict[str, Any] | None = None
        if allow_commit:
            commit_quality = commit_quality_preflight(repo)
            commit_result = create_commit(
                repo,
                f"nexa dev: {mission_goal[:120]}",
                allow_commit=True,
            )
            if commit_result and commit_result.get("ok"):
                commit_hash = rev_parse_head(repo)
                vc = validate_commit(repo)
                if not vc.get("ok"):
                    rb = rollback_last_commit(repo, allow_commit=True)
                    commit_hash = None
                    commit_result = {
                        **commit_result,
                        "ok": False,
                        "post_commit_validation": vc,
                        "rolled_back": rb,
                    }
                    context_accum["commit_validation_failed"] = vc
                    context_accum["commit_rollback"] = rb
            context_accum["commit_quality"] = commit_quality

        push_result: dict[str, Any] | None = None
        if allow_push:
            push_result = {"ok": False, "error": "push_not_implemented_use_manual_git_push"}

        github_pr_result: dict[str, Any] | None = None
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
                "branch": context_accum.get("run_branch"),
                "commit_hash": commit_hash,
                "commit_quality": commit_quality,
            }
            pr_ui = ws_prepare_pr_summary(ws, run_blob)
            gh = create_pull_request(
                goal=mission_goal,
                run_result=run_blob,
                workspace_id=workspace_id,
                repo_path=repo,
                head_branch=str(context_accum.get("run_branch") or "") or None,
            )
            github_pr_result = gh
            if auto_pr:
                pr_ui["auto_pr_requested"] = True
                pr_ui["github_pr"] = gh
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

        pl_sum = (
            f"tests={'ok' if tests_passed else 'fail'}; "
            f"iters={loop_iterations_executed}; "
            f"branch={context_accum.get('run_branch') or '—'}; "
            f"commit={commit_hash or '—'}"
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
            "stagnation_stopped": stagnation_stop,
            "branch": context_accum.get("run_branch"),
            "commit_hash": commit_hash,
            "commit_quality": commit_quality,
            "summary": pl_sum,
            "pipeline_summary": pl_sum,
            "github_pr": github_pr_result,
            "pipeline": {
                "sequence": list(DEV_PIPELINE_SEQUENCE),
                "analyze": {"completed": True},
                "code_test_loop": {
                    "iterations": loop_iterations_executed,
                    "tests_passed": tests_passed,
                    "stagnation_stop": stagnation_stop,
                },
                "commit": {
                    "attempted": bool(allow_commit),
                    "result": commit_result,
                    "hash": commit_hash,
                },
                "pr": {"result": github_pr_result},
            },
        }
        result_payload["pr_ready"] = is_pr_ready({**result_payload, "status": "completed"})
        _fc = classify_dev_failure(
            error_text=None,
            tests_passed=tests_passed,
            adapter_round_ok=not has_runtime_errors,
            privacy_blocked=False,
        )
        result_payload["failure_classification"] = _fc
        result_payload["fix_strategy_hint"] = select_fix_strategy(_fc)

        if tests_passed:
            _notify_progress("Done — tests are green for this pass.")
        elif has_runtime_errors or stagnation_stop:
            _notify_progress("Stopped — see summary for errors or stagnation.")

        result_payload["progress_messages"] = list(progress_messages)

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
            "progress_messages": progress_messages,
            "adapter_used": adapter_used_name,
            "iterations": loop_iterations_executed,
            "tests_passed": tests_passed,
            "pr_ready": result_payload["pr_ready"],
            "has_runtime_errors": has_runtime_errors,
            "pipeline": result_payload.get("pipeline"),
            "failure_classification": result_payload.get("failure_classification"),
            "fix_strategy_hint": result_payload.get("fix_strategy_hint"),
            "branch": result_payload.get("branch"),
            "commit_hash": result_payload.get("commit_hash"),
            "commit_quality": result_payload.get("commit_quality"),
            "summary": result_payload.get("summary"),
            "github_pr": result_payload.get("github_pr"),
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
        _fcb = classify_dev_failure(
            error_text=str(exc),
            tests_passed=False,
            adapter_round_ok=True,
            privacy_blocked=True,
        )
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
            "failure_classification": _fcb,
            "fix_strategy_hint": select_fix_strategy(_fcb),
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
        _fcf = classify_dev_failure(
            error_text=str(exc),
            tests_passed=False,
            adapter_round_ok=False,
            privacy_blocked=False,
        )
        return {
            "ok": False,
            "run_id": rid,
            "status": "failed",
            "error": str(exc),
            "steps": steps_out,
            "progress_messages": progress_messages,
            "iterations": loop_iterations_executed,
            "tests_passed": False,
            "pr_ready": False,
            "has_runtime_errors": True,
            "failure_classification": _fcf,
            "fix_strategy_hint": select_fix_strategy(_fcf),
        }


__all__ = ["DEV_PIPELINE_SEQUENCE", "run_dev_mission"]
