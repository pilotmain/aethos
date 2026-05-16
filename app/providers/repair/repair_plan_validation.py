# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Validate brain-structured repair plans before execution (Phase 2 Step 7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.providers.repair.repair_safe_edits import is_protected_relative_path

_ALLOWED_STEP_TYPES = frozenset({"inspect", "edit", "verify", "shell", "redeploy"})
_ALLOWED_EDIT_OPS = frozenset({"patch", "replace", "append"})
_ALLOWED_PREFIXES = ("npm ", "node ", "python ", "python3 ", "pytest ", "pnpm ", "yarn ")


def _resolve_in_repo(repo: Path, rel: str) -> Path | None:
    rel = (rel or "").strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    target = (repo / rel).resolve()
    try:
        target.relative_to(repo)
    except ValueError:
        return None
    return target


def validate_repair_plan(plan: dict[str, Any], *, repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path).resolve()
    errors: list[str] = []
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("missing_steps")
    norm_steps: list[dict[str, Any]] = []
    if isinstance(steps, list):
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"step_{i}_not_object")
                continue
            stype = str(step.get("type") or "")
            if stype not in _ALLOWED_STEP_TYPES:
                errors.append(f"step_{i}_type_{stype}")
                continue
            if stype == "inspect":
                path = str(step.get("path") or step.get("target") or "package.json")
                if is_protected_relative_path(path):
                    errors.append(f"step_{i}_protected_path")
                elif _resolve_in_repo(repo, path) is None:
                    errors.append(f"step_{i}_path_escape")
                else:
                    norm_steps.append({"type": "inspect", "target": path})
            elif stype == "edit":
                path = str(step.get("path") or "")
                op = str(step.get("operation") or "patch").lower()
                if op not in _ALLOWED_EDIT_OPS:
                    errors.append(f"step_{i}_edit_op")
                elif is_protected_relative_path(path):
                    errors.append(f"step_{i}_protected_edit")
                elif _resolve_in_repo(repo, path) is None:
                    errors.append(f"step_{i}_edit_path_escape")
                elif not str(step.get("content") or step.get("patch") or "").strip() and op != "patch":
                    errors.append(f"step_{i}_edit_empty")
                else:
                    norm_steps.append(
                        {
                            "type": "edit",
                            "path": path,
                            "operation": op,
                            "content": step.get("content"),
                            "patch": step.get("patch"),
                            "reason": str(step.get("reason") or "")[:500],
                        }
                    )
            elif stype == "verify":
                cmd = str(step.get("command") or "")
                if not any(cmd.strip().lower().startswith(p) for p in _ALLOWED_PREFIXES):
                    errors.append(f"step_{i}_verify_cmd")
                else:
                    norm_steps.append({"type": "verify", "command": cmd, "cwd": str(repo)})
            elif stype == "shell":
                cmd = str(step.get("command") or "")
                if not any(cmd.strip().lower().startswith(p) for p in _ALLOWED_PREFIXES):
                    errors.append(f"step_{i}_shell_cmd")
                else:
                    norm_steps.append({"type": "shell", "command": cmd, "cwd": str(repo)})
            elif stype == "redeploy":
                norm_steps.append({"type": "redeploy", "provider": step.get("provider") or "vercel"})
    conf = plan.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if c < 0 or c > 1:
                errors.append("confidence_out_of_range")
        except (TypeError, ValueError):
            errors.append("confidence_invalid")
    return {
        "valid": not errors,
        "errors": errors,
        "normalized_steps": norm_steps,
        "diagnosis": str(plan.get("diagnosis") or "")[:2000],
        "redeploy_after_verify": bool(plan.get("redeploy_after_verify", True)),
    }
