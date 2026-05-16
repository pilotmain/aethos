# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Brain-routed repair planning with deterministic test fallback (Phase 2 Step 6–7)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.brain.repair_brain import needs_brain_escalation, request_repair_plan_from_brain
from app.providers.repair.repair_plan_validation import validate_repair_plan
from app.runtime.runtime_state import ensure_execution_schema, load_runtime_state, save_runtime_state, utc_now_iso


def _read_package_scripts(repo: Path) -> dict[str, str]:
    pkg = repo / "package.json"
    if not pkg.is_file():
        return {}
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts") if isinstance(data, dict) else {}
    if not isinstance(scripts, dict):
        return {}
    return {str(k): str(v) for k, v in scripts.items() if k and v}


def build_deterministic_repair_plan(
    *,
    repair_context: dict[str, Any],
    deploy_ctx: dict[str, Any],
) -> dict[str, Any]:
    repo = Path(str(deploy_ctx.get("repo_path") or "")).resolve()
    scripts = _read_package_scripts(repo)
    diagnosis = repair_context.get("diagnosis") if isinstance(repair_context.get("diagnosis"), dict) else {}
    category = str(diagnosis.get("failure_category") or "unknown")
    steps: list[dict[str, Any]] = [{"type": "inspect", "target": "package.json"}]

    if category in ("dependency_failure", "build_failure") or not (repo / "node_modules").is_dir():
        steps.append({"type": "shell", "command": "npm install", "cwd": str(repo)})

    added_verify = False
    for script_name in ("test", "build", "lint"):
        if script_name in scripts:
            steps.append({"type": "verify", "command": f"npm run {script_name}", "cwd": str(repo)})
            added_verify = True
            break
    if not added_verify and (repo / "package.json").is_file():
        steps.append({"type": "verify", "command": "npm run build", "cwd": str(repo)})

    steps.append({"type": "redeploy", "provider": deploy_ctx.get("provider") or "vercel"})

    plan_id = str(uuid.uuid4())
    return {
        "plan_id": plan_id,
        "repair_context_id": repair_context.get("repair_context_id"),
        "project_id": repair_context.get("project_id"),
        "steps": steps,
        "planner": "deterministic",
        "diagnosis": diagnosis.get("diagnosis"),
        "confidence": diagnosis.get("confidence"),
        "created_at": utc_now_iso(),
    }


def _brain_plan_to_execution_steps(
    brain_plan: dict[str, Any],
    *,
    deploy_ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    validation = brain_plan.get("validation") or {}
    norm = validation.get("normalized_steps") if isinstance(validation, dict) else None
    if not isinstance(norm, list):
        validation = validate_repair_plan(brain_plan, repo_path=str(deploy_ctx.get("repo_path") or ""))
        norm = validation.get("normalized_steps") or []
    steps: list[dict[str, Any]] = list(norm)
    if brain_plan.get("redeploy_after_verify", True):
        if not any(s.get("type") == "redeploy" for s in steps if isinstance(s, dict)):
            steps.append({"type": "redeploy", "provider": deploy_ctx.get("provider") or "vercel"})
    return steps


def build_repair_plan(
    *,
    repair_context: dict[str, Any],
    deploy_ctx: dict[str, Any],
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build repair plan — deterministic when sufficient; escalate to brain when needed.
    """
    diagnosis = repair_context.get("diagnosis") if isinstance(repair_context.get("diagnosis"), dict) else {}
    ev = evidence or {}
    plan_id = str(uuid.uuid4())

    if not needs_brain_escalation(ev, diagnosis):
        plan = build_deterministic_repair_plan(repair_context=repair_context, deploy_ctx=deploy_ctx)
        plan["plan_id"] = plan_id
    else:
        brain_plan, brain_decision = request_repair_plan_from_brain(
            evidence=ev,
            diagnosis=diagnosis,
            repair_context_id=str(repair_context.get("repair_context_id") or ""),
            project_id=str(repair_context.get("project_id") or ""),
        )
        if brain_plan is None:
            plan = build_deterministic_repair_plan(repair_context=repair_context, deploy_ctx=deploy_ctx)
            plan["plan_id"] = plan_id
            plan["planner"] = "deterministic_fallback"
            plan["brain_decision"] = brain_decision
        else:
            steps = _brain_plan_to_execution_steps(brain_plan, deploy_ctx=deploy_ctx)
            planner = str(brain_plan.get("planner") or "brain")
            plan = {
                "plan_id": plan_id,
                "repair_context_id": repair_context.get("repair_context_id"),
                "project_id": repair_context.get("project_id"),
                "steps": steps,
                "planner": planner,
                "diagnosis": brain_plan.get("diagnosis"),
                "confidence": brain_plan.get("confidence"),
                "brain_decision": brain_decision,
                "brain_plan": {
                    "diagnosis": brain_plan.get("diagnosis"),
                    "confidence": brain_plan.get("confidence"),
                    "redeploy_after_verify": brain_plan.get("redeploy_after_verify"),
                },
                "created_at": utc_now_iso(),
            }

    st = load_runtime_state()
    ensure_execution_schema(st)
    ex = st.setdefault("execution", {})
    plans = ex.setdefault("plans", {}) if isinstance(ex, dict) else {}
    if isinstance(plans, dict):
        plans[plan["plan_id"]] = plan
        save_runtime_state(st)
    return plan
