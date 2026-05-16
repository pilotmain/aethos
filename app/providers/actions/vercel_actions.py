# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Vercel CLI-backed actions (Phase 2 Step 4; non-interactive, cwd-scoped)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.deploy_context.context_history import persist_deployment_identity, record_operator_provider_action
from app.providers.actions.provider_action_result import action_result
from app.providers.actions.provider_logs import summarize_cli_streams
from app.providers.provider_cli import run_cli_argv
from app.providers.provider_privacy import redact_cli_output


def _timeout() -> float:
    s = get_settings()
    return float(getattr(s, "aethos_provider_cli_timeout_sec", 20) or 20)


def _repo_cwd(ctx: dict[str, Any]) -> Path:
    return Path(str(ctx.get("repo_path") or "")).resolve()


def _parse_list_payload(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw or "null")
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("deployments", "data", "items"):
            v = data.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _deployment_id_from_row(row: dict[str, Any]) -> str | None:
    for k in ("uid", "id", "deploymentId", "deployment_id"):
        v = row.get(k)
        if v:
            s = str(v).strip()
            if s:
                return s
    return None


def _deployment_url(row: dict[str, Any]) -> str | None:
    for k in ("url",):
        v = row.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v.strip()
    aliases = row.get("alias")
    if isinstance(aliases, list) and aliases:
        a0 = aliases[0]
        if isinstance(a0, str) and a0.startswith("http"):
            return a0
    return None


def _env_filter(rows: list[dict[str, Any]], environment: str) -> list[dict[str, Any]]:
    env = (environment or "production").strip().lower()
    out: list[dict[str, Any]] = []
    for r in rows:
        target = str(r.get("target") or r.get("environment") or "").strip().lower()
        if env == "production" and target in ("production", "prod", ""):
            out.append(r)
        elif env == "preview" and target in ("preview", "staging", ""):
            out.append(r)
        elif not target:
            out.append(r)
    return out or rows


def _fetch_deployment_rows(
    ctx: dict[str, Any], *, environment: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cwd = _repo_cwd(ctx)
    argv = ["vercel", "list", "--format", "json", "--yes", "--cwd", str(cwd)]
    if environment:
        argv.extend(["--environment", environment])
    code, out, err = run_cli_argv(argv, timeout_sec=_timeout(), cwd=cwd)
    rows = _parse_list_payload(out)
    summ = summarize_cli_streams(returncode=code, stdout=out, stderr=err)
    return rows, summ


def list_deployments(ctx: dict[str, Any], *, environment: str = "production") -> dict[str, Any]:
    rows, summ = _fetch_deployment_rows(ctx, environment=environment)
    try:
        rc_int = int(summ.get("returncode", 1))
    except (TypeError, ValueError):
        rc_int = 1
    ok = rc_int == 0 and bool(rows)
    record_operator_provider_action(
        {
            "provider": "vercel",
            "action": "list_deployments",
            "success": ok,
            "project_id": ctx.get("project_id"),
            "failure_category": None if ok else summ.get("failure_category"),
        }
    )
    return {
        **action_result(
            provider="vercel",
            action="list_deployments",
            success=ok,
            project=str(ctx.get("project_id") or ""),
            extra={"deployments": rows[:40], "cli": summ},
        ),
    }


def _latest_row(ctx: dict[str, Any], environment: str) -> dict[str, Any] | None:
    rows, _summ = _fetch_deployment_rows(ctx, environment=environment)
    if not rows:
        return None
    filtered = _env_filter([r for r in rows if isinstance(r, dict)], environment)
    use = filtered or [r for r in rows if isinstance(r, dict)]
    return use[0] if use else None


def deployment_status(ctx: dict[str, Any], *, environment: str = "production") -> dict[str, Any]:
    row = _latest_row(ctx, environment)
    if not row:
        summ = summarize_cli_streams(returncode=1, stdout="", stderr="no_deployments")
        record_operator_provider_action(
            {
                "provider": "vercel",
                "action": "deployment_status",
                "success": False,
                "project_id": ctx.get("project_id"),
                "failure_category": "deployment_failure",
            }
        )
        return {
            **action_result(
                provider="vercel",
                action="deployment_status",
                success=False,
                project=str(ctx.get("project_id") or ""),
                summary="No deployments returned for this environment.",
                extra={"cli": summ},
            ),
        }
    dep_id = _deployment_id_from_row(row)
    url = _deployment_url(row)
    state = str(row.get("state") or row.get("readyState") or "").strip()
    record_operator_provider_action(
        {
            "provider": "vercel",
            "action": "deployment_status",
            "success": True,
            "project_id": ctx.get("project_id"),
            "deployment_id": dep_id,
        }
    )
    return {
        **action_result(
            provider="vercel",
            action="deployment_status",
            success=True,
            project=str(ctx.get("project_id") or ""),
            deployment_id=dep_id,
            url=url,
            summary=f"state={state or 'unknown'}",
            extra={"deployment": row},
        ),
    }


def deployment_logs(ctx: dict[str, Any], *, environment: str = "production", limit: int = 80) -> dict[str, Any]:
    cwd = _repo_cwd(ctx)
    row = _latest_row(ctx, environment)
    dep_id = _deployment_id_from_row(row) if row else None
    argv = ["vercel", "logs", "--yes", "--json", "-n", str(max(10, min(int(limit), 300))), "--cwd", str(cwd)]
    if dep_id:
        argv.append(dep_id)
    if environment:
        argv.extend(["--environment", environment])
    code, out, err = run_cli_argv(argv, timeout_sec=_timeout(), cwd=cwd)
    summ = summarize_cli_streams(returncode=code, stdout=out, stderr=err)
    ok = code == 0
    record_operator_provider_action(
        {
            "provider": "vercel",
            "action": "deployment_logs",
            "success": ok,
            "project_id": ctx.get("project_id"),
            "deployment_id": dep_id,
            "failure_category": None if ok else summ.get("failure_category"),
        }
    )
    return {
        **action_result(
            provider="vercel",
            action="deployment_logs",
            success=ok,
            project=str(ctx.get("project_id") or ""),
            deployment_id=dep_id,
            logs_available=True,
            summary=summ.get("preview"),
            extra={"cli": summ, "raw_json_lines": redact_cli_output((out or "")[:12_000], max_out=12_000)},
        ),
    }


def redeploy_latest(ctx: dict[str, Any], *, environment: str = "production") -> dict[str, Any]:
    cwd = _repo_cwd(ctx)
    row = _latest_row(ctx, environment)
    if not row:
        summ = summarize_cli_streams(returncode=1, stdout="", stderr="no_deployments_to_redeploy")
        record_operator_provider_action(
            {
                "provider": "vercel",
                "action": "redeploy_latest",
                "success": False,
                "project_id": ctx.get("project_id"),
                "failure_category": "deployment_failure",
            }
        )
        return {
            **action_result(
                provider="vercel",
                action="redeploy_latest",
                success=False,
                project=str(ctx.get("project_id") or ""),
                summary="No deployment found to redeploy.",
                extra={"cli": summ},
            ),
        }
    dep_id = _deployment_id_from_row(row) or _deployment_url(row)
    if not dep_id:
        return {
            **action_result(
                provider="vercel",
                action="redeploy_latest",
                success=False,
                project=str(ctx.get("project_id") or ""),
                summary="Could not determine deployment id/url from list output.",
                extra={"deployment": row},
            ),
        }
    argv = ["vercel", "redeploy", str(dep_id), "--yes", "--cwd", str(cwd)]
    code, out, err = run_cli_argv(argv, timeout_sec=max(_timeout(), 120.0), cwd=cwd)
    summ = summarize_cli_streams(returncode=code, stdout=out, stderr=err)
    ok = code == 0
    url = (out or "").strip().splitlines()[-1].strip() if ok else _deployment_url(row)
    if ok and url and not url.startswith("http"):
        url = None
    pid = str(ctx.get("project_id") or "")
    persist_deployment_identity(
        linked_project_id=pid,
        provider="vercel",
        provider_project=str(ctx.get("provider_project") or ""),
        deployment_id=_deployment_id_from_row(row),
        environment=environment,
        repo_path=str(cwd),
        url=url,
    )
    record_operator_provider_action(
        {
            "provider": "vercel",
            "action": "redeploy_latest",
            "success": ok,
            "project_id": pid,
            "deployment_id": _deployment_id_from_row(row),
            "failure_category": None if ok else summ.get("failure_category"),
        }
    )
    return {
        **action_result(
            provider="vercel",
            action="redeploy_latest",
            success=ok,
            project=pid,
            deployment_id=_deployment_id_from_row(row),
            url=url,
            logs_available=True,
            summary=summ.get("preview") if not ok else "Redeploy triggered.",
            extra={"cli": summ},
        ),
    }


def restart_project(ctx: dict[str, Any], *, environment: str = "production") -> dict[str, Any]:
    """Vercel: restart is implemented as redeploy latest (serverless cold start / rebuild)."""
    out = redeploy_latest(ctx, environment=environment)
    out["action"] = "restart_project"
    return out


def inspect_project_cli(ctx: dict[str, Any]) -> dict[str, Any]:
    """Best-effort ``vercel inspect`` when a deployment id is known from list."""
    cwd = _repo_cwd(ctx)
    row = _latest_row(ctx, "production")
    dep_id = _deployment_id_from_row(row) if row else None
    if not dep_id:
        return action_result(
            provider="vercel",
            action="inspect_project",
            success=False,
            project=str(ctx.get("project_id") or ""),
            summary="No deployment id available for inspect.",
        )
    argv = ["vercel", "inspect", dep_id, "--yes", "--cwd", str(cwd)]
    code, out, err = run_cli_argv(argv, timeout_sec=_timeout(), cwd=cwd)
    summ = summarize_cli_streams(returncode=code, stdout=out, stderr=err)
    return {
        **action_result(
            provider="vercel",
            action="inspect_project",
            success=code == 0,
            project=str(ctx.get("project_id") or ""),
            deployment_id=dep_id,
            summary=summ.get("preview"),
            extra={"cli": summ},
        ),
    }
