# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Brain-routed repair planning with deterministic test fallback (Phase 2 Step 6)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

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
    category = str((repair_context.get("diagnosis") or {}).get("failure_category") or "unknown")
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
    plan = {
        "plan_id": plan_id,
        "repair_context_id": repair_context.get("repair_context_id"),
        "project_id": repair_context.get("project_id"),
        "steps": steps,
        "planner": "deterministic",
        "created_at": utc_now_iso(),
    }
    return plan


def build_repair_plan(
    *,
    repair_context: dict[str, Any],
    deploy_ctx: dict[str, Any],
) -> dict[str, Any]:
    """
    Build repair plan — deterministic when ``USE_REAL_LLM=false`` or ``NEXA_PYTEST=1``.
    """
    use_llm = (os.environ.get("USE_REAL_LLM") or "").strip().lower() in ("1", "true", "yes", "on")
    pytest = (os.environ.get("NEXA_PYTEST") or "").strip() in ("1", "true", "yes")
    if use_llm and not pytest:
        # Optional LLM path: fall back to deterministic until wired to brain router.
        pass
    plan = build_deterministic_repair_plan(repair_context=repair_context, deploy_ctx=deploy_ctx)
    st = load_runtime_state()
    ensure_execution_schema(st)
    ex = st.setdefault("execution", {})
    plans = ex.setdefault("plans", {}) if isinstance(ex, dict) else {}
    if isinstance(plans, dict):
        plans[plan["plan_id"]] = plan
        save_runtime_state(st)
    return plan
