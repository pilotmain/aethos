# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CLI entrypoint: ``python -m aethos_cli`` — AethOS HTTP API client (Phase 21)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _base_url() -> str:
    return (
        os.environ.get("AETHOS_API_BASE")
        or os.environ.get("NEXA_API_BASE")
        or os.environ.get("API_BASE_URL")
        or "http://127.0.0.1:8010"
    ).rstrip("/")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_serve(host: str, port: int, reload: bool) -> int:
    """Run uvicorn from the repo root (native dev)."""
    root = _repo_root()
    env = os.environ.copy()
    env.setdefault("AETHOS_API_BASE", f"http://127.0.0.1:{port}")
    env.setdefault("NEXA_API_BASE", f"http://127.0.0.1:{port}")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    print(f"Starting API from {root} — http://{host}:{port}", file=sys.stderr)
    return subprocess.call(cmd, cwd=str(root), env=env)


def _headers(uid: str) -> dict[str, str]:
    h = {"X-User-Id": uid, "Accept": "application/json"}
    tok = (
        os.environ.get("AETHOS_WEB_API_TOKEN") or os.environ.get("NEXA_WEB_API_TOKEN") or ""
    ).strip()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _req(
    method: str,
    path: str,
    *,
    uid: str,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, str]:
    url = f"{_base_url()}{path}"
    h = _headers(uid)
    if content_type:
        h["Content-Type"] = content_type
    elif body is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.getcode(), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def merge_settings_payload(base: dict[str, Any], pairs: list[str]) -> dict[str, Any]:
    """Merge key=value pairs onto a GET /user/settings JSON document for POST."""
    ui = dict(base.get("ui_preferences") or {})
    out_priv = base.get("privacy_mode")
    for p in pairs:
        k, _, v = p.partition("=")
        k, v = k.strip(), v.strip()
        if not k:
            continue
        if k == "privacy_mode":
            out_priv = v
        elif k == "theme":
            ui["theme"] = v
        elif k == "auto_refresh":
            ui["auto_refresh"] = v.lower() in ("1", "true", "yes", "on")
    payload: dict[str, Any] = {"ui_preferences": ui}
    if out_priv is not None:
        payload["privacy_mode"] = out_priv
    return payload


def cmd_settings_get(uid: str) -> int:
    code, body = _req("GET", "/api/v1/user/settings", uid=uid)
    print(body)
    return 0 if code == 200 else 1


def cmd_settings_set(uid: str, pairs: list[str]) -> int:
    code0, b0 = _req("GET", "/api/v1/user/settings", uid=uid)
    if code0 != 200:
        print(b0, file=sys.stderr)
        return 1
    cur = json.loads(b0)
    merged = merge_settings_payload(cur, pairs)
    payload = json.dumps(merged).encode()
    code1, b1 = _req("POST", "/api/v1/user/settings", uid=uid, body=payload)
    print(b1)
    return 0 if code1 == 200 else 1


def cmd_dev_workspace_add(uid: str, name: str, path: str) -> int:
    payload = json.dumps({"name": name, "repo_path": path}).encode()
    code, body = _req("POST", "/api/v1/dev/workspaces", uid=uid, body=payload)
    print(body[:24000])
    return 0 if code == 200 else 1


def cmd_dev_run(
    uid: str,
    *,
    workspace_id: str,
    goal: str,
    agent: str | None,
    allow_write: bool,
    allow_commit: bool,
    auto_pr: bool,
    max_iterations: int | None,
) -> int:
    body_obj: dict[str, Any] = {
        "workspace_id": workspace_id,
        "goal": goal,
        "allow_write": allow_write,
        "allow_commit": allow_commit,
        "auto_pr": auto_pr,
    }
    if agent:
        body_obj["preferred_agent"] = agent
    if max_iterations is not None:
        body_obj["max_iterations"] = max_iterations
    code, body = _req("POST", "/api/v1/dev/runs", uid=uid, body=json.dumps(body_obj).encode())
    print(body[:24000])
    return 0 if code == 200 else 1


def cmd_dev_schedule(
    uid: str,
    *,
    workspace_id: str,
    goal: str,
    cron: str | None,
    interval_seconds: int | None,
    agent: str | None,
) -> int:
    sched: dict[str, Any] = {}
    if cron:
        sched["cron"] = cron
    elif interval_seconds is not None:
        sched["interval_seconds"] = interval_seconds
    else:
        print("Provide --cron or --interval-seconds", file=sys.stderr)
        return 1
    body_obj: dict[str, Any] = {
        "workspace_id": workspace_id,
        "goal": goal,
        "schedule": sched,
    }
    if agent:
        body_obj["preferred_agent"] = agent
    code, body = _req("POST", "/api/v1/dev/runs", uid=uid, body=json.dumps(body_obj).encode())
    print(body[:24000])
    return 0 if code == 200 else 1


def cmd_replay(uid: str, mission_id: str) -> int:
    mid = urllib.parse.quote(mission_id, safe="")
    code, body = _req(
        "POST",
        f"/api/v1/mission-control/replay/{mid}",
        uid=uid,
        body=b"{}",
    )
    print(f"HTTP {code}")
    print(body[:24000])
    return 0 if code == 200 else 1


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(_repo_root() / ".env")
    except Exception:
        pass
    try:
        from app.core.aethos_env import apply_aethos_env_aliases

        apply_aethos_env_aliases()
    except Exception:
        pass

    _prog = os.path.basename(sys.argv[0]) if sys.argv else "aethos"
    if _prog == "__main__.py":
        _prog = "aethos"
    p = argparse.ArgumentParser(prog=_prog, description="AethOS — CLI (HTTP API client)")
    p.add_argument(
        "--no-banner",
        action="store_true",
        help="Skip ASCII banner on stderr (or set AETHOS_CLI_NO_BANNER=1 / NEXA_CLI_NO_BANNER=1)",
    )
    p.add_argument(
        "--user-id",
        default=os.environ.get("AETHOS_CLI_USER_ID")
        or os.environ.get("NEXA_CLI_USER_ID")
        or "cli_user",
        help="X-User-Id header (or env AETHOS_CLI_USER_ID / NEXA_CLI_USER_ID)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "onboard",
        help="First-time operator onboarding (same as: aethos setup)",
    )

    sp_gateway = sub.add_parser(
        "gateway",
        help="Run the persistent AethOS HTTP gateway (same stack as: aethos serve)",
    )
    sp_gateway.add_argument("--host", default="0.0.0.0")
    sp_gateway.add_argument(
        "--port",
        type=int,
        default=int(
            os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010"
        ),
    )
    sp_gateway.add_argument("--reload", action="store_true")

    sp_message = sub.add_parser("message", help="Gateway message dispatch (AethOS runtime)")
    msg_sub = sp_message.add_subparsers(dest="message_cmd", required=True)
    sp_msg_send = msg_sub.add_parser("send", help="POST mission-control/gateway/run")
    sp_msg_send.add_argument("text", help="User message body")
    sp_msg_send.add_argument(
        "--workflow",
        action="store_true",
        help="Enqueue persistent tool workflow instead of chat.",
    )
    sp_msg_send.add_argument(
        "--wait",
        action="store_true",
        help="After enqueue, drive local dispatch loop until terminal (requires local ~/.aethos state).",
    )
    sp_msg_send.add_argument("--timeout", type=int, default=120, help="With --wait, max seconds (default 120)")
    sp_msg_send.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Print JSON only (no truncation banner).",
    )

    sp_task = sub.add_parser("task", help="Runtime workflow task inspection")
    task_sub = sp_task.add_subparsers(dest="task_cmd", required=True)
    sp_task_show = task_sub.add_parser("show", help="GET /api/v1/runtime/tasks/{task_id}")
    sp_task_show.add_argument("task_id")

    sp_priv = sub.add_parser("privacy", help="Phase 2 privacy / PII API (HTTP)")
    priv_sub = sp_priv.add_subparsers(dest="privacy_cmd", required=True)
    priv_sub.add_parser("status", help="GET /api/v1/privacy/status")
    priv_sub.add_parser("audit", help="GET /api/v1/privacy/audit")
    sp_priv_scan = priv_sub.add_parser("scan", help="POST /api/v1/privacy/scan")
    sp_priv_scan.add_argument(
        "scan_path",
        nargs="?",
        default="",
        metavar="PATH",
        help="Optional file or directory to scan (e.g. .); else --text or stdin",
    )
    sp_priv_scan.add_argument("--text", default="", help="Inline text (if no PATH and no stdin)")
    sp_priv_redact = priv_sub.add_parser("redact", help="POST /api/v1/privacy/redact")
    sp_priv_redact.add_argument("--text", default="", help="Text to redact (default: stdin)")
    sp_priv_ev = priv_sub.add_parser("evaluate-egress", help="POST /api/v1/privacy/evaluate-egress")
    sp_priv_ev.add_argument("--text", default="", help="Text to evaluate (default: stdin)")
    sp_priv_ev.add_argument("--boundary", default="http", help="Boundary label (default http)")
    sp_priv_mode = priv_sub.add_parser("mode", help="GET /api/v1/privacy/policy (+ optional env hint)")
    sp_priv_mode.add_argument(
        "target_mode",
        nargs="?",
        default="",
        help="Optional desired mode (not persisted; set AETHOS_PRIVACY_MODE and restart)",
    )

    sp_prov = sub.add_parser("providers", help="Provider CLI inventory (Phase 2 Step 3)")
    prov_sub = sp_prov.add_subparsers(dest="providers_cmd", required=True)
    prov_sub.add_parser("list", help="GET /api/v1/providers")
    prov_sub.add_parser("scan", help="POST /api/v1/providers/scan")
    sp_prov_show = prov_sub.add_parser("show", help="GET /api/v1/providers/{id}")
    sp_prov_show.add_argument("provider_id")
    sp_prov_proj = prov_sub.add_parser("projects", help="GET /api/v1/providers/{id}/projects")
    sp_prov_proj.add_argument("provider_id")
    prov_sub.add_parser("trust", help="GET /api/v1/mission-control/providers/trust")
    prov_sub.add_parser("governance", help="GET /api/v1/mission-control/providers/governance")
    prov_sub.add_parser("history", help="GET /api/v1/mission-control/providers/history")
    prov_sub.add_parser("overview", help="GET /api/v1/mission-control/providers/overview")

    sp_proj = sub.add_parser("projects", help="Local project registry (Phase 2 Step 3)")
    proj_sub = sp_proj.add_subparsers(dest="projects_cmd", required=True)
    proj_sub.add_parser("list", help="GET /api/v1/projects")
    proj_sub.add_parser("scan", help="POST /api/v1/projects/scan")
    sp_proj_show = proj_sub.add_parser("show", help="GET /api/v1/projects/{id}")
    sp_proj_show.add_argument("project_id")
    sp_proj_link = proj_sub.add_parser("link", help="POST /api/v1/projects/{id}/link")
    sp_proj_link.add_argument("project_id")
    sp_proj_link.add_argument("repo_path", help="Absolute path to repo root")
    sp_proj_resolve = proj_sub.add_parser("resolve", help="POST /api/v1/projects/{id}/resolve")
    sp_proj_resolve.add_argument("project_id")
    sp_proj_resolve.add_argument("--env", default="production", dest="environment", help="production | preview")
    sp_proj_conf = proj_sub.add_parser("confidence", help="GET /api/v1/projects/{id}/confidence")
    sp_proj_conf.add_argument("project_id")

    sp_deploy = sub.add_parser("deploy", help="Provider-backed deploy operations (Phase 2 Step 4)")
    dep_op = sp_deploy.add_subparsers(dest="deploy_cmd", required=True)
    sp_dr = dep_op.add_parser("restart", help="POST /api/v1/providers/vercel/restart")
    sp_dr.add_argument("project_id")
    sp_dr.add_argument("--env", default="production", dest="environment", help="production | preview")
    sp_dd = dep_op.add_parser("redeploy", help="POST /api/v1/providers/vercel/redeploy")
    sp_dd.add_argument("project_id")
    sp_dd.add_argument("--env", default="production", dest="environment", help="production | preview")
    sp_ds = dep_op.add_parser("status", help="GET /api/v1/providers/vercel/status")
    sp_ds.add_argument("project_id")
    sp_ds.add_argument("--env", default="production", dest="environment", help="production | preview")
    sp_dl = dep_op.add_parser("logs", help="GET /api/v1/providers/vercel/logs")
    sp_dl.add_argument("project_id")
    sp_dl.add_argument("--env", default="production", dest="environment", help="production | preview")
    sp_dl.add_argument("--limit", type=int, default=80, help="Log line limit (10–300)")
    sp_dfx = dep_op.add_parser("fix-and-redeploy", help="POST /api/v1/projects/{id}/fix-and-redeploy")
    sp_dfx.add_argument("project_id")
    sp_dfx.add_argument("--env", default="production", dest="environment", help="production | preview")

    sp_proj_repair = proj_sub.add_parser("repair", help="POST /api/v1/projects/{id}/repair")
    sp_proj_repair.add_argument("project_id")
    sp_proj_repair.add_argument("--env", default="production", dest="environment", help="production | preview")
    sp_proj_lr = proj_sub.add_parser("latest-repair", help="GET /api/v1/projects/{id}/latest-repair")
    sp_proj_lr.add_argument("project_id")

    sp_dep = sub.add_parser("deployments", help="Deployment runtime API")
    dep_sub = sp_dep.add_subparsers(dest="dep_cmd", required=True)
    dep_sub.add_parser("list", help="GET /api/v1/deployments")
    sp_dep_show = dep_sub.add_parser("show", help="GET /api/v1/deployments/{id}")
    sp_dep_show.add_argument("deployment_id")
    sp_dep_logs = dep_sub.add_parser("logs", help="GET /api/v1/deployments/{id}/logs")
    sp_dep_logs.add_argument("deployment_id")
    sp_dep_art = dep_sub.add_parser("artifacts", help="GET /api/v1/deployments/{id}/artifacts")
    sp_dep_art.add_argument("deployment_id")
    sp_dep_rb = dep_sub.add_parser("rollback", help="POST /api/v1/deployments/{id}/rollback")
    sp_dep_rb.add_argument("deployment_id")
    sp_dep_rb.add_argument("--reason", default="", help="Optional rollback reason")

    sp_env = sub.add_parser("environments", help="Environment runtime API")
    env_sub = sp_env.add_subparsers(dest="env_cmd", required=True)
    env_sub.add_parser("list", help="GET /api/v1/environments")
    env_sub.add_parser("locks", help="GET /api/v1/environments/locks")
    sp_env_show = env_sub.add_parser("show", help="GET /api/v1/environments/{id}")
    sp_env_show.add_argument("environment_id")

    sp_runtime = sub.add_parser("runtime", help="Unified runtime cohesion (Phase 3 Step 11–12)")
    rt_sub = sp_runtime.add_subparsers(dest="runtime_cmd", required=True)
    from aethos_cli.cli_parser_helpers import add_runtime_parser_once

    _runtime_parser_names: set[str] = set()

    add_runtime_parser_once(rt_sub, _runtime_parser_names, "health", help="GET /api/v1/mission-control/runtime/health")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "timeline", help="GET /api/v1/mission-control/runtime/timeline")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "recommendations", help="GET /api/v1/mission-control/runtime-recommendations")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "workers", help="GET /api/v1/mission-control/runtime-workers")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "performance", help="GET /api/v1/mission-control/runtime/performance")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "cache", help="Hydration cache metrics from runtime state")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "hydration-metrics", help="Incremental hydration metrics (local)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "latency", help="Operational responsiveness summary")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "scalability", help="GET /api/v1/mission-control/runtime/scalability")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "payload-discipline", help="Payload discipline metrics (local)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "pressure-overview", help="Operational pressure overview (MC scalability)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "accountability", help="GET /api/v1/mission-control/runtime/accountability")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "escalations", help="GET /api/v1/mission-control/runtime/escalations")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "overview", help="GET /api/v1/mission-control/runtime/overview")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "trust", help="GET /api/v1/mission-control/governance/trust")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "continuity", help="GET /api/v1/mission-control/runtime/continuity (Phase 4 Step 5)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "calmness-mc", help="GET /api/v1/mission-control/runtime/calmness")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "readiness", help="GET /api/v1/mission-control/runtime/readiness")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "strategy", help="GET /api/v1/mission-control/runtime/strategy")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "maturity", help="GET /api/v1/mission-control/runtime/maturity")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "evolution", help="GET /api/v1/mission-control/runtime/evolution")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "trends", help="GET /api/v1/mission-control/runtime/trends")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "forecasts", help="GET /api/v1/mission-control/runtime/forecasts")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "outlook", help="GET /api/v1/mission-control/runtime/outlook")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "trajectory", help="GET /api/v1/mission-control/runtime/trajectory")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "optimization", help="GET /api/v1/mission-control/runtime/optimization")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "projections", help="GET /api/v1/mission-control/runtime/projections")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "intelligence", help="GET /api/v1/mission-control/runtime/intelligence (Phase 4 Step 5)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "posture", help="GET /api/v1/runtime/production-posture (falls back to MC runtime/posture)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "recovery", help="GET /api/v1/mission-control/runtime/recovery")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "routing", help="GET /api/v1/mission-control/runtime/routing")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "advisories", help="GET /api/v1/mission-control/runtime/advisories")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "focus", help="GET /api/v1/mission-control/runtime/focus")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "ping", help="GET /api/v1/health + runtime capabilities")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "hydration", help="GET /api/v1/runtime/hydration queue/status")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "responsiveness", help="GET /api/v1/runtime/responsiveness")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "throttling", help="GET /api/v1/runtime/throttling")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "payloads", help="GET /api/v1/runtime/payloads profile metrics")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "eras", help="GET /api/v1/runtime/eras long-horizon continuity")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "summaries", help="GET /api/v1/runtime/summaries enterprise summaries")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "partitions", help="GET /api/v1/runtime/partitions")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "calmness-lock", help="GET /api/v1/runtime/calmness-lock integrity")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "story", help="GET /api/v1/mission-control/runtime-story")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "explainability", help="GET /api/v1/mission-control/explainability")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "routing-adaptive", help="GET /api/v1/runtime/routing adaptive provider visibility")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "restarts", help="GET /api/v1/runtime/restarts restart history")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "identity", help="GET /api/v1/runtime/identity brand lock state")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "launch-focus", help="GET /api/v1/runtime/operational-focus (Step 13)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "priority-work", help="GET /api/v1/runtime/priority-work")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "launch-cert", help="GET /api/v1/runtime/launch-certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "certification", help="GET /api/v1/runtime/certification (Step 14 RC bundle)")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "release-candidate", help="GET /api/v1/runtime/release-candidate")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "enterprise-grade", help="GET /api/v1/runtime/enterprise-grade")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "readiness-progress", help="GET /api/v1/runtime/readiness-progress")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "startup", help="GET /api/v1/runtime/startup progressive stages")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "bootstrap", help="GET /api/v1/runtime/bootstrap MC payload")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "compatibility", help="GET /api/v1/runtime/compatibility")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "branding-audit", help="GET /api/v1/runtime/branding-audit")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "ownership", help="Runtime ownership + telegram polling coordination")
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "ownership-authority", help="GET /api/v1/runtime/ownership-authority"
    )
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "process-integrity", help="GET /api/v1/runtime/process-integrity")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "database-integrity", help="GET /api/v1/runtime/database-integrity")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "recovery-authority", help="GET /api/v1/runtime/recovery-authority")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "startup-integrity", help="GET /api/v1/runtime/startup-integrity")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "truth-authority", help="GET /api/v1/runtime/truth-authority")
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "integrity-final", help="GET /api/v1/runtime/runtime-integrity-final"
    )
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "supervise", help="Authoritative runtime supervision summary")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "stop", help="Stop runtime process groups (API, bot, hydration)")
    sp_rt_restart = add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "restart", help="Restart runtime process groups"
    )
    sp_rt_restart.add_argument("--clean", action="store_true", help="Force clean shutdown before restart")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "recover", help="Recover ownership, DB, and process conflicts")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "services", help="Local API/web/bot process registry")
    sp_rt_takeover = add_runtime_parser_once(rt_sub, _runtime_parser_names, "takeover", help="Force runtime ownership for this CLI session")
    sp_rt_takeover.add_argument("--yes", action="store_true", help="Confirm takeover without prompt")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "release", help="Release runtime + telegram locks if owned")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "status", help="Unified runtime operational status")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "authority", help="Operational + Mission Control authority")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "integrity", help="Runtime integrity certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "confidence", help="Operator confidence summary")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "truth", help="Truth integrity and consistency")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "assurance", help="Enterprise runtime assurance bundle")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "continuity-cert", help="Runtime continuity certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "persistence", help="Runtime persistence health")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "production-cert", help="Runtime production certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "operational-story", help="Coherent operational narratives")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "stability", help="Runtime stability coordination")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "long-session", help="Long-session reliability certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "office", help="Office operational authority")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "memory-discipline", help="Operational memory discipline")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "degraded", help="Degraded mode finalization")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "continuity-confidence", help="Operator continuity confidence")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "responsiveness-guarantees", help="Enterprise responsiveness guarantees")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "freeze", help="Runtime release freeze lock")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "enterprise-cert", help="Final enterprise operational certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "operational-story-final", help="Unified operational story final")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "certify", help="Production cut certification bundle")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "governance", help="GET /api/v1/runtime/governance-authority")
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "autonomous-coordination", help="GET /api/v1/runtime/autonomous-coordination"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "governance-timeline", help="GET /api/v1/runtime/governance-timeline"
    )
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "pressure", help="GET /api/v1/runtime/pressure-governance")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "enterprise-safety", help="GET /api/v1/runtime/enterprise-safety")
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "trust-finalization", help="GET /api/v1/runtime/trust-finalization"
    )
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "truth-governance", help="GET /api/v1/runtime/truth-governance")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "final-cert", help="GET /api/v1/runtime/final-certification")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "command-authority", help="GET /api/v1/runtime/command-authority")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "unified-narrative", help="GET /api/v1/runtime/unified-narrative")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "visibility", help="GET /api/v1/runtime/visibility-authority")
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "readiness-convergence", help="GET /api/v1/runtime/readiness-convergence"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "stability-finalization", help="GET /api/v1/runtime/stability-finalization"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "recovery-experience", help="GET /api/v1/runtime/recovery-experience"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "governance-consolidation", help="GET /api/v1/runtime/governance-consolidation"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "enterprise-confidence", help="GET /api/v1/runtime/enterprise-confidence"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "finalization-cert", help="GET /api/v1/runtime/finalization-certification"
    )
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "launch", help="Enterprise runtime launch orchestration")
    add_runtime_parser_once(rt_sub, _runtime_parser_names, "startup-status", help="GET /api/v1/runtime/startup-status")
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "startup-recovery", help="GET /api/v1/runtime/startup-recovery"
    )
    add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "launch-experience", help="GET /api/v1/runtime/launch-experience"
    )
    sp_ecosystem = sub.add_parser("ecosystem", help="Operational intelligence ecosystem (Phase 4 Step 3)")
    eco_sub = sp_ecosystem.add_subparsers(dest="ecosystem_cmd", required=True)
    eco_sub.add_parser("health", help="GET /api/v1/mission-control/ecosystem/health")
    eco_sub.add_parser("maturity", help="GET /api/v1/mission-control/ecosystem/maturity")
    sp_enterprise = sub.add_parser("enterprise", help="Enterprise runtime evolution overview (Phase 4)")
    ent_sub = sp_enterprise.add_subparsers(dest="enterprise_cmd", required=True)
    ent_sub.add_parser("overview", help="GET /api/v1/mission-control/executive-overview (Step 9)")
    ent_sub.add_parser("strategy", help="GET /api/v1/mission-control/enterprise/strategy")
    ent_sub.add_parser("intelligence", help="GET /api/v1/mission-control/enterprise/intelligence")
    ent_sub.add_parser("posture", help="GET /api/v1/mission-control/enterprise/posture (Phase 4 Step 5)")
    sp_ent_mem = ent_sub.add_parser("memory", help="Enterprise operational memory from runtime truth")
    sp_ent_mem.add_argument("--json", action="store_true", help="Raw JSON only")
    sp_automation = sub.add_parser("automation", help="Automation effectiveness (Phase 4)")
    auto_sub = sp_automation.add_subparsers(dest="automation_cmd", required=True)
    auto_sub.add_parser("effectiveness", help="GET /api/v1/mission-control/automation/effectiveness")
    sp_op_ready = sub.add_parser("operational-readiness", help="Enterprise operational readiness bundle")
    sp_rt_narr = sub.add_parser("operational-narrative", help="Operational narratives from runtime truth")
    sp_exec_vis = sub.add_parser("execution", help="Execution visibility (Phase 3 Step 14)")
    exec_sub = sp_exec_vis.add_subparsers(dest="execution_cmd", required=True)
    exec_sub.add_parser("visibility", help="GET /api/v1/mission-control/execution/visibility")

    sp_opsum = sub.add_parser("operational", help="Operational summary (Phase 3 Step 11)")
    op_sub = sp_opsum.add_subparsers(dest="operational_cmd", required=True)
    op_sub.add_parser("summary", help="GET /api/v1/mission-control/operational-summary")
    op_sub.add_parser("trends", help="GET /api/v1/mission-control/runtime/trends")
    op_sub.add_parser("trajectory", help="GET /api/v1/mission-control/runtime/trajectory")
    op_sub.add_parser("memory", help="Enterprise operational memory from runtime truth")

    sp_intel = sub.add_parser("intelligence", help="Operational intelligence (Phase 3 Step 10)")
    intel_sub = sp_intel.add_subparsers(dest="intelligence_cmd", required=True)
    intel_sub.add_parser("summary", help="GET /api/v1/mission-control/operational-intelligence")
    intel_sub.add_parser("risks", help="GET /api/v1/mission-control/governance/risks")
    sp_intel_rec = intel_sub.add_parser("recommendations", help="GET …/runtime-recommendations")
    sp_intel_rec.add_argument("--json", action="store_true", help="Raw JSON only")

    sp_gov = sub.add_parser("governance", help="Runtime governance (Phase 3 Step 10)")
    gov_sub = sp_gov.add_subparsers(dest="governance_cmd", required=True)
    gov_sub.add_parser("timeline", help="GET /api/v1/mission-control/governance")
    gov_sub.add_parser("risks", help="GET /api/v1/mission-control/governance/risks")
    gov_sub.add_parser("summary", help="GET /api/v1/mission-control/governance/summary")
    gov_sub.add_parser("trust", help="GET /api/v1/mission-control/governance/trust")
    gov_sub.add_parser("overview", help="GET /api/v1/mission-control/governance/overview")
    gov_sub.add_parser("accountability", help="GET /api/v1/mission-control/governance/accountability")
    gov_sub.add_parser("maturity", help="GET /api/v1/mission-control/governance/maturity")
    gov_sub.add_parser("progression", help="GET /api/v1/mission-control/governance/progression")
    gov_sub.add_parser("intelligence", help="GET /api/v1/mission-control/governance/intelligence")
    gov_sub.add_parser("index", help="GET /api/v1/mission-control/governance/index")
    gov_sub.add_parser("experience", help="GET /api/v1/mission-control/governance-experience")
    sp_gov_search = gov_sub.add_parser("search", help="GET /api/v1/mission-control/governance/search")
    sp_gov_search.add_argument("query", nargs="?", default=None)
    sp_gov_filter = gov_sub.add_parser("filter", help="GET /api/v1/mission-control/governance/filter")
    sp_gov_filter.add_argument("--kind", default=None)
    sp_gov_filter.add_argument("--actor", default=None)
    sp_gov_filter.add_argument("--provider", default=None)
    sp_tl_win = add_runtime_parser_once(
        rt_sub, _runtime_parser_names, "timeline-window", help="GET /api/v1/mission-control/timeline/window"
    )
    sp_tl_win.add_argument("--offset", type=int, default=0)
    sp_tl_win.add_argument("--limit", type=int, default=24)
    sp_wk_sum = sub.add_parser("worker-summaries", help="Paginated worker summaries")
    sp_wk_sum.add_argument("--page", type=int, default=1)

    sp_mkt = sub.add_parser("marketplace", help="Marketplace automation packs")
    mkt_sub = sp_mkt.add_subparsers(dest="marketplace_cmd", required=True)
    mkt_sub.add_parser("packs", help="GET /api/v1/mission-control/automation-packs")
    mkt_sub.add_parser("trust", help="GET /api/v1/mission-control/automation/trust")
    sp_mkt_run = mkt_sub.add_parser("run-pack", help="POST …/automation-packs/{id}/run")
    sp_mkt_run.add_argument("pack_id")

    sp_workspace = sub.add_parser("workspace", help="Workspace intelligence (Phase 3 Step 9)")
    ws_sub = sp_workspace.add_subparsers(dest="workspace_cmd", required=True)
    ws_sub.add_parser("summary", help="GET /api/v1/mission-control/workspace-intelligence")
    ws_sub.add_parser("risks", help="GET /api/v1/mission-control/workspace-risks")
    ws_sub.add_parser("health", help="GET /api/v1/mission-control/runtime/health (enterprise categories)")
    sp_ws_chains = ws_sub.add_parser("research-chains", help="GET …/research-chains")
    sp_ws_chains.add_argument("--project-id", default=None, dest="project_id")

    sp_workers = sub.add_parser("workers", help="Runtime worker detail (Phase 3 Step 8)")
    wk_sub = sp_workers.add_subparsers(dest="workers_cmd", required=True)
    wk_sub.add_parser("list", help="GET /api/v1/mission-control/runtime-workers")
    sp_wk_show = wk_sub.add_parser("show", help="GET /api/v1/mission-control/runtime-workers/{id}")
    sp_wk_show.add_argument("worker_id")
    sp_wk_del = wk_sub.add_parser("deliverables", help="GET …/runtime-workers/{id}/deliverables")
    wk_sub.add_parser("accountability", help="GET /api/v1/mission-control/workers/accountability")
    wk_sub.add_parser("overview", help="GET /api/v1/mission-control/workers/overview")
    wk_sub.add_parser("effectiveness", help="GET /api/v1/mission-control/workers/effectiveness")
    wk_sub.add_parser("ecosystem", help="GET /api/v1/mission-control/workers/ecosystem")
    wk_sub.add_parser("coordination", help="GET /api/v1/mission-control/workers/coordination")
    wk_sub.add_parser("intelligence", help="GET /api/v1/mission-control/workers/intelligence (Phase 4 Step 5)")
    wk_sub.add_parser("archive", help="GET /api/v1/mission-control/workers/archive")
    sp_wk_del.add_argument("worker_id")
    sp_wk_cont = wk_sub.add_parser("continuity", help="GET …/operator-continuity + worker context")
    sp_wk_cont.add_argument("worker_id")

    sp_dlv = sub.add_parser("deliverables", help="Worker deliverables (Phase 3 Step 8)")
    dlv_sub = sp_dlv.add_subparsers(dest="deliverables_cmd", required=True)
    dlv_sub.add_parser("list", help="GET /api/v1/mission-control/deliverables")
    sp_dlv_show = dlv_sub.add_parser("show", help="GET /api/v1/mission-control/deliverables/{id}")
    sp_dlv_show.add_argument("deliverable_id")
    sp_dlv_exp = dlv_sub.add_parser("export", help="GET …/deliverables/{id}/export")
    sp_dlv_exp.add_argument("deliverable_id")
    sp_dlv_exp.add_argument("--format", default="markdown", choices=("markdown", "text", "json"))
    sp_dlv_cmp = dlv_sub.add_parser("compare", help="Compare two deliverables (runtime truth)")
    sp_dlv_cmp.add_argument("deliverable_id_a")
    sp_dlv_cmp.add_argument("deliverable_id_b")

    sp_agents = sub.add_parser("agents", help="Coordination agent API (multi-agent parity)")
    ag_sub = sp_agents.add_subparsers(dest="agents_cmd", required=True)
    ag_sub.add_parser("list", help="GET /api/v1/runtime/agents/")
    sp_ag_show = ag_sub.add_parser("show", help="GET /api/v1/runtime/agents/{id}")
    sp_ag_show.add_argument("agent_id")
    sp_ag_tasks = ag_sub.add_parser("tasks", help="GET /api/v1/runtime/agents/{id}/tasks")
    sp_ag_tasks.add_argument("agent_id")

    sp_planning = sub.add_parser("planning", help="Adaptive planning runtime API")
    plan_sub = sp_planning.add_subparsers(dest="planning_cmd", required=True)
    plan_sub.add_parser("list", help="GET /api/v1/runtime/planning")
    sp_plan_show = plan_sub.add_parser("show", help="GET /api/v1/runtime/planning/{planning_id}")
    sp_plan_show.add_argument("planning_id")

    sp_optimization = sub.add_parser(
        "optimization",
        help="Runtime optimization snapshot (parity baseline; default: metrics)",
    )
    opt_sub = sp_optimization.add_subparsers(dest="optimization_cmd", required=False)
    opt_sub.add_parser("metrics", help="GET /api/v1/runtime/optimization")

    sp_ops = sub.add_parser("operations", help="Operational workflow queue API")
    ops_sub = sp_ops.add_subparsers(dest="ops_cmd", required=True)
    ops_sub.add_parser("list", help="GET /api/v1/operations")
    ops_sub.add_parser("supervisors", help="GET /api/v1/runtime/supervisors")
    ops_sub.add_parser("loops", help="GET /api/v1/runtime/loops")
    sp_ops_run = ops_sub.add_parser("run", help="POST /api/v1/operations/run")
    sp_ops_run.add_argument("op_type", help="deploy | rollback | health_check | …")
    sp_ops_run.add_argument("--environment-id", default=None, dest="environment_id")

    sp_logs = sub.add_parser(
        "logs",
        help="Tail logs: optional category gateway|agents|…|planning|reasoning|optimization|replanning|adaptive_execution|delegation_optimization|… (runtime = ~/.aethos/aethos.json)",
    )
    sp_logs.add_argument(
        "log_category",
        nargs="?",
        default=None,
        metavar="CATEGORY",
        help="gateway | agents | ... | planning | reasoning | optimization | replanning | adaptive_execution | delegation_optimization | tools | workflows | runtime_events | runtime_sessions | runtime_metrics",
    )
    sp_logs.add_argument("--lines", type=int, default=80, dest="log_lines")

    sub.add_parser(
        "doctor",
        help="Diagnostics: compileall + optional API health",
    )
    sub.add_parser(
        "repair",
        help="Repair runtime ownership, database coordination, and process conflicts",
    )

    sp_state = sub.add_parser("state", help="GET mission-control/state")
    sp_state.add_argument("--mission-user", default=None, help="Query user_id scope")

    sp_run = sub.add_parser("run", help="POST mission-control/gateway/run")
    sp_run.add_argument("text", help="Mission text")

    sp_replay = sub.add_parser("replay", help="POST mission-control/replay/{mission_id}")
    sp_replay.add_argument("mission_id")

    sp_settings = sub.add_parser("settings", help="User settings API")
    ss = sp_settings.add_subparsers(dest="settings_cmd", required=True)
    ss.add_parser("get", help="GET /api/v1/user/settings")
    sp_set = ss.add_parser("set", help="POST merged settings (key=value …)")
    sp_set.add_argument(
        "pairs",
        nargs="+",
        metavar="KEY=VALUE",
        help="e.g. privacy_mode=strict theme=dark auto_refresh=true",
    )

    sp_soul = sub.add_parser(
        "soul",
        help="Soul versioning: snapshots under ~/.aethos/soul_history/<user>/ after soul edits",
    )
    soul_sub = sp_soul.add_subparsers(dest="soul_cmd", required=True)
    soul_sub.add_parser("history", help="List snapshot timestamps (newest first)")
    ss_add = soul_sub.add_parser("add", help="Append a line to soul (Mission Control memory API)")
    ss_add.add_argument("text", nargs="+", help="Rule or paragraph text")
    ss_diff = soul_sub.add_parser("diff", help="Unified diff: snapshot vs current soul from API")
    ss_diff.add_argument(
        "version",
        help="Snapshot stem e.g. 2026-05-13_00-26-31_123456 (see: aethos soul history)",
    )
    ss_rb = soul_sub.add_parser("rollback", help="Restore soul from snapshot via API")
    ss_rb.add_argument(
        "version",
        help="Snapshot stem from `aethos soul history`",
    )

    sp_dev = sub.add_parser("dev", help="POST /api/v1/dev/* (workspaces + runs)")
    dev_sub = sp_dev.add_subparsers(dest="dev_cmd", required=True)
    sp_dws = dev_sub.add_parser("workspace-add", help="POST /dev/workspaces")
    sp_dws.add_argument("--name", required=True)
    sp_dws.add_argument("--path", required=True, dest="repo_path")
    sp_drn = dev_sub.add_parser("run", help="POST /dev/runs")
    sp_drn.add_argument("--workspace", required=True, dest="workspace_id")
    sp_drn.add_argument("--goal", required=True)
    sp_drn.add_argument("--agent", default=None)
    sp_drn.add_argument("--allow-write", action="store_true")
    sp_drn.add_argument("--allow-commit", action="store_true")
    sp_drn.add_argument("--auto-pr", action="store_true")
    sp_drn.add_argument("--max-iterations", type=int, default=None, dest="max_iterations")
    sp_dsc = dev_sub.add_parser("schedule", help="POST /dev/runs with schedule payload")
    sp_dsc.add_argument("--workspace", required=True, dest="workspace_id")
    sp_dsc.add_argument("--goal", required=True)
    sp_dsc.add_argument("--cron", default=None)
    sp_dsc.add_argument("--interval-seconds", type=int, default=None, dest="interval_seconds")
    sp_dsc.add_argument("--agent", default=None)

    sp_skills = sub.add_parser("skills", help="Plugin skills registry (Phase 6)")
    sk_sub = sp_skills.add_subparsers(dest="skills_cmd", required=True)
    sk_sub.add_parser("list", help="List registered plugin skills")
    sk_ins = sk_sub.add_parser("install", help="Install skill from file or URL")
    sk_ins.add_argument("name")
    sk_ins.add_argument(
        "source",
        nargs="?",
        default="clawhub",
        help="clawhub | file:///path/to/skill.yaml | https://…",
    )
    sk_rem = sk_sub.add_parser("remove", help="Remove skill (stub)")
    sk_rem.add_argument("name")

    try:
        from app.cli.clawhub import register_clawhub_parser

        register_clawhub_parser(sub)
    except ModuleNotFoundError:
        # `app` not on PYTHONPATH (minimal install / wrong CWD) — skip remote registry subcommands.
        pass

    try:
        from app.cli.plugin import register_plugin_parser

        register_plugin_parser(sub)
    except ModuleNotFoundError:
        pass

    sp_scrape = sub.add_parser(
        "scrape",
        help="Phase 21 web scraping (local fetch/extract; subcommands: fetch, extract, paginate)",
    )
    sp_scrape.add_argument(
        "scrape_argv",
        nargs=argparse.REMAINDER,
        metavar="ARGS",
        help='e.g. fetch https://example.com  |  extract https://example.com --css "h1"',
    )

    sp_cron = sub.add_parser("cron", help="Cron automation API (Phase 13; requires NEXA_CRON_API_TOKEN)")
    cr_sub = sp_cron.add_subparsers(dest="cron_cmd", required=True)
    cr_sub.add_parser("list", help="GET /cron/jobs")
    cr_add = cr_sub.add_parser("add", help="POST channel_message job")
    cr_add.add_argument("cron_expression")
    cr_add.add_argument("message", nargs="+", help="Message text")
    cr_rem = cr_sub.add_parser("remove", help="DELETE job")
    cr_rem.add_argument("job_id")
    cr_pau = cr_sub.add_parser("pause")
    cr_pau.add_argument("job_id")
    cr_res = cr_sub.add_parser("resume")
    cr_res.add_argument("job_id")

    sub.add_parser("run-dev", help="Deprecated alias; use: aethos dev run …")

    sp_setup = sub.add_parser(
        "setup",
        help="Interactive enterprise setup wizard (writes .env keys; see docs/ENTERPRISE_SETUP.md)",
    )
    setup_sub = sp_setup.add_subparsers(dest="setup_cmd")
    setup_sub.add_parser("resume", help="Resume incomplete setup from saved state")
    sp_setup_repair = setup_sub.add_parser("repair", help="Repair install (reinstall deps + rewrite core keys)")
    setup_sub.add_parser("wizard", help="Run full setup wizard (default)")
    setup_sub.add_parser("doctor", help="Enterprise setup health + integration detection")
    setup_sub.add_parser("validate", help="Validate setup completeness (.env, auth, onboarding)")
    setup_sub.add_parser("onboarding", help="Orchestrator-first onboarding conversation")
    setup_sub.add_parser("certify", help="One-curl + ready-state + production cut certification")
    setup_sub.add_parser("coverage", help="Enterprise setup systems coverage report")
    setup_sub.add_parser("status", help="Setup completeness status")
    setup_sub.add_parser("continuity", help="Setup resume / continuity state")
    setup_sub.add_parser("startup", help="Enterprise startup orchestration from setup")
    setup_sub.add_parser("operational-recovery", help="Setup operational recovery guidance")
    setup_sub.add_parser("first-impression", help="Mission Control first-impression bundle")

    sp_restart = sub.add_parser("restart", help="Restart API, web, or bot processes")
    restart_sub = sp_restart.add_subparsers(dest="restart_cmd")
    restart_sub.add_parser("api", help="Restart API (uvicorn)")
    restart_sub.add_parser("web", help="Restart Mission Control (Next.js)")
    restart_sub.add_parser("bot", help="Restart Telegram bot")
    restart_sub.add_parser("connection", help="Repair connection + health check")
    restart_sub.add_parser("runtime", help="Restart API, web, and refresh runtime connection")
    restart_sub.add_parser("all", help="Restart API and web (default)")

    sp_connect = sub.add_parser("connect", help="Refresh Mission Control connection credentials")
    sp_connection = sub.add_parser("connection", help="Mission Control connection profile")
    conn_sub = sp_connection.add_subparsers(dest="connection_cmd", required=True)
    conn_sub.add_parser("show", help="Show redacted connection profile")
    conn_sub.add_parser("repair", help="Regenerate bearer token and repair creds")
    conn_sub.add_parser("diagnose", help="Diagnose API health and runtime capabilities")
    conn_sub.add_parser("reset", help="Reset connection profile and repair credentials")

    sp_cloud = sub.add_parser("cloud", help="Manage ~/.aethos/clouds.yaml deploy providers")
    cloud_sub = sp_cloud.add_subparsers(dest="cloud_cmd", required=True)
    cloud_sub.add_parser("list", help="List provider slugs")
    sp_cloud_add = cloud_sub.add_parser("add", help="Add or replace a provider")
    sp_cloud_add.add_argument("name", help="Slug, e.g. myvps")
    sp_cloud_add.add_argument("--deploy-cmd", required=True)
    sp_cloud_add.add_argument("--pre-deploy", default=None)
    sp_cloud_add.add_argument("--login-cmd", default=None)
    sp_cloud_add.add_argument("--login-probe", default=None)
    sp_cloud_add.add_argument("--url-pattern", default=None)
    sp_cloud_add.add_argument("--deploy-cmd-preview", default=None)
    sp_cloud_rm = cloud_sub.add_parser("remove", help="Remove a provider by slug")
    sp_cloud_rm.add_argument("name")

    sub.add_parser(
        "init-db",
        help="Ensure SQLite dir exists and apply schema (ensure_schema); same DB as API + Telegram bot",
    )

    sub.add_parser(
        "unify-db",
        help="Phase 60 — merge legacy SQLite files into ~/.aethos/data/aethos.db and align DATABASE_URL",
    )

    sp_mscopes = sub.add_parser(
        "migrate-scopes",
        help="Phase 61 — optional SQLite rewrite of bare tg_* parent_chat_id to web:tg_*:default (see --apply)",
    )
    sp_mscopes.add_argument(
        "--apply",
        action="store_true",
        help="Run UPDATE (default: dry-run listing only)",
    )

    sub.add_parser(
        "configure-bot",
        help="Phase 62 — write ~/.aethos/.env with canonical DATABASE_URL + orchestration (matches API bot DB)",
    )

    sub.add_parser(
        "start",
        help="Start AethOS (alias for: aethos runtime launch)",
    )
    sub.add_parser(
        "stop",
        help="Stop AethOS runtime (alias for: aethos runtime stop)",
    )
    sub.add_parser(
        "restart",
        help="Restart AethOS runtime (alias for: aethos runtime restart)",
    )

    sub.add_parser(
        "status",
        help="HTTP health checks against AETHOS_API_BASE / NEXA_API_BASE (default :8010)",
    )
    sub.add_parser("features", help="Show enabled capability flags from repo .env")

    sp_conf = sub.add_parser("config", help="Print path to repo .env (optional --edit with $EDITOR)")
    sp_conf.add_argument("--edit", action="store_true", help="Open in $EDITOR when set")

    sp_pr = sub.add_parser(
        "pr",
        help="Automated GitHub PR review (Phase 23; requires GITHUB_TOKEN + NEXA_PR_REVIEW_ENABLED)",
    )
    pr_sub = sp_pr.add_subparsers(dest="pr_cmd", required=True)
    sp_prev = pr_sub.add_parser("review", help="Analyze PR and post GitHub review")
    sp_prev.add_argument("repo", help="owner/repo")
    sp_prev.add_argument("pr_number", type=int)

    sp_serve = sub.add_parser(
        "serve",
        help="Run FastAPI locally via uvicorn (default port 8010; matches docker-compose host mapping)",
    )
    sp_serve.add_argument("--host", default="0.0.0.0", help="Bind address")
    sp_serve.add_argument(
        "--port",
        type=int,
        default=int(
            os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010"
        ),
        help="Listen port (or env AETHOS_SERVE_PORT / NEXA_SERVE_PORT)",
    )
    sp_serve.add_argument("--reload", action="store_true", help="Uvicorn --reload")

    args = p.parse_args()
    uid = str(args.user_id)

    if (
        not args.no_banner
        and args.cmd
        in (
            "serve",
            "setup",
            "init-db",
            "unify-db",
            "migrate-scopes",
            "configure-bot",
            "cloud",
            "onboard",
            "gateway",
            "doctor",
        )
    ):
        from aethos_cli.banner import maybe_print_sponsor_hint, print_banner, should_show_banner

        if should_show_banner():
            print_banner()
            maybe_print_sponsor_hint()

    if args.cmd == "onboard":
        from aethos_cli.setup_wizard import run_setup_wizard

        return run_setup_wizard()

    if args.cmd == "gateway":
        return cmd_serve(str(args.host), int(args.port), bool(args.reload))

    if args.cmd == "message":
        if args.message_cmd == "send":
            body_obj: dict[str, Any] = {"text": args.text, "user_id": uid}
            if getattr(args, "workflow", False):
                body_obj["workflow"] = True
            payload = json.dumps(body_obj).encode()
            code, body = _req(
                "POST",
                "/api/v1/mission-control/gateway/run",
                uid=uid,
                body=payload,
            )
            if code == 200 and getattr(args, "workflow", False) and getattr(args, "wait", False):
                try:
                    data = json.loads(body)
                    tid = str(data.get("task_id") or "")
                    if tid:
                        from app.orchestration import runtime_dispatcher
                        from app.orchestration import task_registry
                        from app.runtime.runtime_state import load_runtime_state, save_runtime_state

                        deadline = time.time() + max(1, int(getattr(args, "timeout", 120) or 120))
                        while time.time() < deadline:
                            st = load_runtime_state()
                            t = task_registry.get_task(st, tid)
                            stt = str((t or {}).get("state") or "")
                            if stt in ("completed", "failed", "cancelled"):
                                break
                            runtime_dispatcher.dispatch_once(st)
                            save_runtime_state(st)
                            time.sleep(0.02)
                        st2 = load_runtime_state()
                        t2 = task_registry.get_task(st2, tid)
                        data["final_state"] = (t2 or {}).get("state")
                        body = json.dumps(data, indent=2)
                except Exception as exc:
                    body = f"{body}\n(wait loop failed: {exc})"
            if getattr(args, "json_out", False):
                print(body)
            else:
                print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "task":
        if args.task_cmd == "show":
            tid = urllib.parse.quote(str(args.task_id), safe="")
            code, body = _req("GET", f"/api/v1/runtime/tasks/{tid}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "privacy":
        if args.privacy_cmd == "status":
            code, body = _req("GET", "/api/v1/privacy/status", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.privacy_cmd == "audit":
            code, body = _req("GET", "/api/v1/privacy/audit", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.privacy_cmd == "scan":
            from pathlib import Path

            from app.privacy.privacy_path_scan import aggregate_text_for_scan

            scan_path = (getattr(args, "scan_path", "") or "").strip()
            txt = (getattr(args, "text", "") or "").strip()
            if scan_path:
                txt = aggregate_text_for_scan(Path(scan_path))
            elif not txt:
                txt = sys.stdin.read()
            payload = json.dumps({"text": txt}).encode()
            code, body = _req("POST", "/api/v1/privacy/scan", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.privacy_cmd == "redact":
            txt = (getattr(args, "text", "") or "").strip()
            if not txt:
                txt = sys.stdin.read()
            payload = json.dumps({"text": txt}).encode()
            code, body = _req("POST", "/api/v1/privacy/redact", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.privacy_cmd == "evaluate-egress":
            txt = (getattr(args, "text", "") or "").strip()
            if not txt:
                txt = sys.stdin.read()
            bnd = (getattr(args, "boundary", "") or "http").strip() or "http"
            payload = json.dumps({"text": txt, "boundary": bnd}).encode()
            code, body = _req("POST", "/api/v1/privacy/evaluate-egress", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.privacy_cmd == "mode":
            code, body = _req("GET", "/api/v1/privacy/policy", uid=uid)
            print(body[:24000])
            want = (getattr(args, "target_mode", "") or "").strip()
            if want and code == 200:
                print(
                    f"To use mode {want!r}, set AETHOS_PRIVACY_MODE={want} in the repo .env and restart the API.",
                    file=sys.stderr,
                )
            return 0 if code == 200 else 1

    if args.cmd == "providers":
        if args.providers_cmd == "list":
            code, body = _req("GET", "/api/v1/providers", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "scan":
            code, body = _req("POST", "/api/v1/providers/scan", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "show":
            pid = urllib.parse.quote(str(args.provider_id), safe="")
            code, body = _req("GET", f"/api/v1/providers/{pid}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "projects":
            pid = urllib.parse.quote(str(args.provider_id), safe="")
            code, body = _req("GET", f"/api/v1/providers/{pid}/projects", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "trust":
            code, body = _req("GET", "/api/v1/mission-control/providers/trust", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "governance":
            code, body = _req("GET", "/api/v1/mission-control/providers/governance", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "history":
            code, body = _req("GET", "/api/v1/mission-control/providers/history", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.providers_cmd == "overview":
            code, body = _req("GET", "/api/v1/mission-control/providers/overview", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "operational-narrative":
        code, body = _req("GET", "/api/v1/mission-control/runtime/narratives", uid=uid)
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "operational-readiness":
        code, body = _req("GET", "/api/v1/mission-control/operational-readiness", uid=uid)
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "projects":
        if args.projects_cmd == "list":
            code, body = _req("GET", "/api/v1/projects", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "scan":
            code, body = _req("POST", "/api/v1/projects/scan", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "show":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            code, body = _req("GET", f"/api/v1/projects/{pid}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "link":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            payload = json.dumps({"repo_path": str(args.repo_path)}).encode()
            code, body = _req("POST", f"/api/v1/projects/{pid}/link", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "resolve":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            env = (getattr(args, "environment", None) or "production").strip()
            payload = json.dumps({"provider": "vercel", "environment": env}).encode()
            code, body = _req("POST", f"/api/v1/projects/{pid}/resolve", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "confidence":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            code, body = _req("GET", f"/api/v1/projects/{pid}/confidence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "repair":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            env = (getattr(args, "environment", None) or "production").strip()
            payload = json.dumps({"provider": "vercel", "environment": env}).encode()
            code, body = _req("POST", f"/api/v1/projects/{pid}/repair", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.projects_cmd == "latest-repair":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            code, body = _req("GET", f"/api/v1/projects/{pid}/latest-repair", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "deploy":
        env = (getattr(args, "environment", None) or "production").strip()
        qenv = urllib.parse.quote(env, safe="")
        pj = urllib.parse.quote(str(args.project_id), safe="")
        if args.deploy_cmd == "restart":
            payload = json.dumps({"project_id": str(args.project_id), "environment": env}).encode()
            code, body = _req("POST", "/api/v1/providers/vercel/restart", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deploy_cmd == "redeploy":
            payload = json.dumps({"project_id": str(args.project_id), "environment": env}).encode()
            code, body = _req("POST", "/api/v1/providers/vercel/redeploy", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deploy_cmd == "status":
            qs = f"?project_id={pj}&environment={qenv}"
            code, body = _req("GET", f"/api/v1/providers/vercel/status{qs}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deploy_cmd == "logs":
            lim = int(getattr(args, "limit", 80) or 80)
            qs = f"?project_id={pj}&environment={qenv}&limit={lim}"
            code, body = _req("GET", f"/api/v1/providers/vercel/logs{qs}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deploy_cmd == "fix-and-redeploy":
            pid = urllib.parse.quote(str(args.project_id), safe="")
            payload = json.dumps({"provider": "vercel", "environment": env}).encode()
            code, body = _req("POST", f"/api/v1/projects/{pid}/fix-and-redeploy", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "deployments":
        if args.dep_cmd == "list":
            code, body = _req("GET", "/api/v1/deployments", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.dep_cmd == "show":
            did = urllib.parse.quote(str(args.deployment_id), safe="")
            code, body = _req("GET", f"/api/v1/deployments/{did}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.dep_cmd == "logs":
            did = urllib.parse.quote(str(args.deployment_id), safe="")
            code, body = _req("GET", f"/api/v1/deployments/{did}/logs", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.dep_cmd == "artifacts":
            did = urllib.parse.quote(str(args.deployment_id), safe="")
            code, body = _req("GET", f"/api/v1/deployments/{did}/artifacts", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.dep_cmd == "rollback":
            did = urllib.parse.quote(str(args.deployment_id), safe="")
            payload = json.dumps({"reason": str(getattr(args, "reason", "") or "")}).encode()
            code, body = _req("POST", f"/api/v1/deployments/{did}/rollback", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "environments":
        if args.env_cmd == "list":
            code, body = _req("GET", "/api/v1/environments", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.env_cmd == "locks":
            code, body = _req("GET", "/api/v1/environments/locks", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.env_cmd == "show":
            eid = urllib.parse.quote(str(args.environment_id), safe="")
            code, body = _req("GET", f"/api/v1/environments/{eid}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "runtime":
        _rt_json = (os.environ.get("AETHOS_RUNTIME_JSON") or "").strip().lower() in ("1", "true", "yes")

        def _rt_print(path: str) -> int:
            code, body = _req("GET", path, uid=uid)
            if code != 200:
                print(body[:8000])
                return 1
            if _rt_json:
                print(body[:24000])
                return 0
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                print(body[:24000])
                return 0
            for key in (
                "runtime_status",
                "runtime_health_summary",
                "runtime_readiness_authority",
                "operational_authority",
                "runtime_integrity_certification",
                "operator_confidence",
                "runtime_truth_consistency",
            ):
                if key in data and isinstance(data[key], dict):
                    block = data[key]
                    msg = block.get("operator_message") or block.get("summary") or block.get("state")
                    if msg:
                        print(msg)
                    for k in ("state", "score", "enterprise_ready", "safe_for_operator", "integrity_score"):
                        if k in block:
                            print(f"  {k}: {block[k]}")
                    return 0
            print(body[:24000])
            return 0

        if args.runtime_cmd == "status":
            return _rt_print("/api/v1/runtime/status")
        if args.runtime_cmd == "health":
            return _rt_print("/api/v1/runtime/health-summary")
        if args.runtime_cmd == "authority":
            return _rt_print("/api/v1/runtime/operational-authority")
        if args.runtime_cmd == "integrity":
            return _rt_print("/api/v1/runtime/integrity-certification")
        if args.runtime_cmd == "confidence":
            return _rt_print("/api/v1/runtime/operator-confidence")
        if args.runtime_cmd == "truth":
            return _rt_print("/api/v1/runtime/truth-consistency")
        if args.runtime_cmd == "assurance":
            return _rt_print("/api/v1/runtime/assurance")
        if args.runtime_cmd == "continuity-cert":
            return _rt_print("/api/v1/runtime/continuity-certification")
        if args.runtime_cmd == "persistence":
            return _rt_print("/api/v1/runtime/persistence-health")
        if args.runtime_cmd == "production-cert":
            return _rt_print("/api/v1/runtime/production-certification")
        if args.runtime_cmd == "operational-story":
            return _rt_print("/api/v1/runtime/operational-story")
        if args.runtime_cmd == "stability":
            return _rt_print("/api/v1/runtime/stability")
        if args.runtime_cmd == "long-session":
            return _rt_print("/api/v1/runtime/long-session")
        if args.runtime_cmd == "office":
            return _rt_print("/api/v1/runtime/office-authority")
        if args.runtime_cmd == "memory-discipline":
            return _rt_print("/api/v1/runtime/memory-discipline")
        if args.runtime_cmd == "degraded":
            return _rt_print("/api/v1/runtime/degraded-mode")
        if args.runtime_cmd == "continuity-confidence":
            return _rt_print("/api/v1/runtime/continuity-confidence")
        if args.runtime_cmd == "responsiveness-guarantees":
            return _rt_print("/api/v1/runtime/responsiveness")
        if args.runtime_cmd == "freeze":
            return _rt_print("/api/v1/runtime/release-freeze")
        if args.runtime_cmd == "enterprise-cert":
            return _rt_print("/api/v1/runtime/enterprise-certification")
        if args.runtime_cmd == "operational-story-final":
            return _rt_print("/api/v1/runtime/operational-story-final")
        if args.runtime_cmd == "timeline":
            code, body = _req("GET", "/api/v1/mission-control/runtime/timeline", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "recommendations":
            code, body = _req("GET", "/api/v1/mission-control/runtime-recommendations", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "workers":
            code, body = _req("GET", "/api/v1/mission-control/runtime-workers", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "performance":
            code, body = _req("GET", "/api/v1/runtime/performance", uid=uid)
            if code != 200:
                code, body = _req("GET", "/api/v1/mission-control/runtime/performance", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "payloads":
            code, body = _req("GET", "/api/v1/runtime/payloads", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "hydration":
            code, body = _req("GET", "/api/v1/runtime/hydration", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "responsiveness":
            code, body = _req("GET", "/api/v1/runtime/responsiveness", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "throttling":
            code, body = _req("GET", "/api/v1/runtime/throttling", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "pressure-overview":
            code, body = _req("GET", "/api/v1/mission-control/runtime/scalability", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "pressure":
            return _rt_print("/api/v1/runtime/pressure-governance")
        if args.runtime_cmd == "governance":
            return _rt_print("/api/v1/runtime/governance-authority")
        if args.runtime_cmd == "autonomous-coordination":
            return _rt_print("/api/v1/runtime/autonomous-coordination")
        if args.runtime_cmd == "governance-timeline":
            return _rt_print("/api/v1/runtime/governance-timeline")
        if args.runtime_cmd == "enterprise-safety":
            return _rt_print("/api/v1/runtime/enterprise-safety")
        if args.runtime_cmd == "trust-finalization":
            return _rt_print("/api/v1/runtime/trust-finalization")
        if args.runtime_cmd == "truth-governance":
            return _rt_print("/api/v1/runtime/truth-governance")
        if args.runtime_cmd == "final-cert":
            return _rt_print("/api/v1/runtime/final-certification")
        if args.runtime_cmd == "command-authority":
            return _rt_print("/api/v1/runtime/command-authority")
        if args.runtime_cmd == "unified-narrative":
            return _rt_print("/api/v1/runtime/unified-narrative")
        if args.runtime_cmd == "visibility":
            return _rt_print("/api/v1/runtime/visibility-authority")
        if args.runtime_cmd == "readiness-convergence":
            return _rt_print("/api/v1/runtime/readiness-convergence")
        if args.runtime_cmd == "stability-finalization":
            return _rt_print("/api/v1/runtime/stability-finalization")
        if args.runtime_cmd == "recovery-experience":
            return _rt_print("/api/v1/runtime/recovery-experience")
        if args.runtime_cmd == "governance-consolidation":
            return _rt_print("/api/v1/runtime/governance-consolidation")
        if args.runtime_cmd == "enterprise-confidence":
            return _rt_print("/api/v1/runtime/enterprise-confidence")
        if args.runtime_cmd == "finalization-cert":
            return _rt_print("/api/v1/runtime/finalization-certification")
        if args.runtime_cmd == "launch":
            from aethos_cli.runtime_launch_cli import cmd_runtime_launch

            return cmd_runtime_launch()
        if args.runtime_cmd == "startup-status":
            from aethos_cli.runtime_launch_cli import cmd_runtime_startup_status

            return cmd_runtime_startup_status()
        if args.runtime_cmd == "startup-recovery":
            from aethos_cli.runtime_launch_cli import cmd_runtime_startup_recovery

            return cmd_runtime_startup_recovery()
        if args.runtime_cmd == "launch-experience":
            from aethos_cli.runtime_launch_cli import cmd_runtime_launch_experience

            return cmd_runtime_launch_experience()
        if args.runtime_cmd == "accountability":
            code, body = _req("GET", "/api/v1/mission-control/runtime/accountability", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "escalations":
            code, body = _req("GET", "/api/v1/mission-control/runtime/escalations", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "overview":
            code, body = _req("GET", "/api/v1/mission-control/runtime/overview", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "trust":
            code, body = _req("GET", "/api/v1/runtime/operator-trust", uid=uid)
            if code == 200:
                return _rt_print("/api/v1/runtime/operator-trust")
            code, body = _req("GET", "/api/v1/mission-control/governance/trust", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd in ("calmness", "calmness-mc"):
            code, body = _req("GET", "/api/v1/mission-control/runtime/calmness", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "readiness":
            code, body = _req("GET", "/api/v1/runtime/readiness-authority", uid=uid)
            if code == 200:
                return _rt_print("/api/v1/runtime/readiness-authority")
            code, body = _req("GET", "/api/v1/mission-control/runtime/readiness", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "strategy":
            code, body = _req("GET", "/api/v1/mission-control/runtime/strategy", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "maturity":
            code, body = _req("GET", "/api/v1/mission-control/runtime/maturity", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "evolution":
            code, body = _req("GET", "/api/v1/mission-control/runtime/evolution", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "trends":
            code, body = _req("GET", "/api/v1/mission-control/runtime/trends", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "forecasts":
            code, body = _req("GET", "/api/v1/mission-control/runtime/forecasts", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "outlook":
            code, body = _req("GET", "/api/v1/mission-control/runtime/outlook", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "trajectory":
            code, body = _req("GET", "/api/v1/mission-control/runtime/trajectory", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "optimization":
            code, body = _req("GET", "/api/v1/mission-control/runtime/optimization", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "projections":
            code, body = _req("GET", "/api/v1/mission-control/runtime/projections", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "intelligence":
            code, body = _req("GET", "/api/v1/mission-control/runtime/intelligence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "posture":
            code, body = _req("GET", "/api/v1/runtime/production-posture", uid=uid)
            if code != 200:
                code, body = _req("GET", "/api/v1/mission-control/runtime/posture", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "eras":
            code, body = _req("GET", "/api/v1/runtime/eras", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "summaries":
            code, body = _req("GET", "/api/v1/runtime/summaries", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "partitions":
            code, body = _req("GET", "/api/v1/runtime/partitions", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd in ("calmness-lock",):
            code, body = _req("GET", "/api/v1/runtime/calmness-lock", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "story":
            code, body = _req("GET", "/api/v1/mission-control/runtime-story", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "explainability":
            code, body = _req("GET", "/api/v1/runtime/explainability", uid=uid)
            if code == 200:
                return _rt_print("/api/v1/runtime/explainability")
            code, body = _req("GET", "/api/v1/mission-control/explainability", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd in ("routing-adaptive",):
            code, body = _req("GET", "/api/v1/runtime/routing", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "restarts":
            code, body = _req("GET", "/api/v1/runtime/restarts", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "identity":
            code, body = _req("GET", "/api/v1/runtime/identity", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "launch-focus":
            code, body = _req("GET", "/api/v1/runtime/operational-focus", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "priority-work":
            code, body = _req("GET", "/api/v1/runtime/priority-work", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "launch-cert":
            code, body = _req("GET", "/api/v1/runtime/launch-certification", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "certification":
            code, body = _req("GET", "/api/v1/runtime/certification", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "release-candidate":
            code, body = _req("GET", "/api/v1/runtime/release-candidate", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "enterprise-grade":
            code, body = _req("GET", "/api/v1/runtime/enterprise-grade", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "readiness-progress":
            code, body = _req("GET", "/api/v1/runtime/readiness-progress", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "startup":
            code, body = _req("GET", "/api/v1/runtime/startup", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "bootstrap":
            code, body = _req("GET", "/api/v1/runtime/bootstrap", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "compatibility":
            code, body = _req("GET", "/api/v1/runtime/compatibility", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "branding-audit":
            code, body = _req("GET", "/api/v1/runtime/branding-audit", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "ownership":
            from aethos_cli.runtime_process_cli import cmd_runtime_ownership

            return cmd_runtime_ownership()
        if args.runtime_cmd == "services":
            from aethos_cli.runtime_process_cli import cmd_runtime_services

            return cmd_runtime_services()
        if args.runtime_cmd == "takeover":
            from aethos_cli.runtime_process_cli import cmd_runtime_takeover

            return cmd_runtime_takeover(yes=bool(getattr(args, "yes", False)))
        if args.runtime_cmd == "release":
            from aethos_cli.runtime_process_cli import cmd_runtime_release

            return cmd_runtime_release()
        if args.runtime_cmd == "stop":
            from aethos_cli.runtime_process_cli import cmd_runtime_stop

            return cmd_runtime_stop()
        if args.runtime_cmd == "restart":
            from aethos_cli.runtime_process_cli import cmd_runtime_restart

            return cmd_runtime_restart(clean=bool(getattr(args, "clean", False)))
        if args.runtime_cmd == "recover":
            from aethos_cli.runtime_process_cli import cmd_runtime_recover

            return cmd_runtime_recover()
        if args.runtime_cmd == "supervise":
            from aethos_cli.runtime_process_cli import cmd_runtime_supervise

            return cmd_runtime_supervise()
        if args.runtime_cmd == "ownership-authority":
            return _rt_print("/api/v1/runtime/ownership-authority")
        if args.runtime_cmd == "process-integrity":
            return _rt_print("/api/v1/runtime/process-integrity")
        if args.runtime_cmd == "database-integrity":
            return _rt_print("/api/v1/runtime/database-integrity")
        if args.runtime_cmd == "recovery-authority":
            return _rt_print("/api/v1/runtime/recovery-authority")
        if args.runtime_cmd == "startup-integrity":
            return _rt_print("/api/v1/runtime/startup-integrity")
        if args.runtime_cmd == "truth-authority":
            return _rt_print("/api/v1/runtime/truth-authority")
        if args.runtime_cmd == "integrity-final":
            return _rt_print("/api/v1/runtime/runtime-integrity-final")
        if args.runtime_cmd == "certify":
            import json
            from app.services.setup.production_cut_certification import build_production_cut_certification

            cert = build_production_cut_certification()
            print(json.dumps(cert, indent=2, default=str)[:32000])
            pc = cert.get("production_cut_certification") or {}
            return 0 if pc.get("production_cut_ready") else 1
        if args.runtime_cmd == "recovery":
            code, body = _req("GET", "/api/v1/mission-control/runtime/recovery", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd in ("routing", "routing-mc"):
            code, body = _req("GET", "/api/v1/mission-control/runtime/routing", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "continuity":
            code, body = _req("GET", "/api/v1/mission-control/runtime/continuity", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "advisories":
            code, body = _req("GET", "/api/v1/mission-control/runtime/advisories", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "focus":
            code, body = _req("GET", "/api/v1/mission-control/runtime/focus", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd == "ping":
            code, body = _req("GET", "/api/v1/health", uid=uid)
            print(body[:4000])
            code2, body2 = _req("GET", "/api/v1/runtime/capabilities", uid=uid)
            print(body2[:4000])
            return 0 if code == 200 and code2 == 200 else 1
        if args.runtime_cmd == "timeline-window":
            off = int(getattr(args, "offset", 0))
            lim = int(getattr(args, "limit", 24))
            code, body = _req("GET", f"/api/v1/mission-control/timeline/window?offset={off}&limit={lim}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd in ("cache", "hydration-metrics", "latency", "scalability"):
            from app.services.mission_control.runtime_hydration import (
                build_runtime_performance_block,
                get_hydration_metrics,
            )
            from app.services.mission_control.runtime_metrics_discipline import get_runtime_discipline_metrics

            h = get_hydration_metrics()
            perf = build_runtime_performance_block(float(h.get("last_hydration_ms") or 0), int(h.get("last_payload_bytes") or 0))
            disc = get_runtime_discipline_metrics()
            if args.runtime_cmd == "cache":
                out = {"hydration_metrics": h, "discipline": disc, "performance": perf}
            elif args.runtime_cmd == "hydration-metrics":
                out = h
            elif args.runtime_cmd == "latency":
                out = {
                    "last_hydration_ms": h.get("last_hydration_ms"),
                    "last_truth_build_ms": disc.get("last_truth_build_ms"),
                    "target_cached_read_ms": 500,
                }
            elif args.runtime_cmd == "scalability":
                code, body = _req("GET", "/api/v1/mission-control/runtime/scalability", uid=uid)
                print(body[:24000])
                return 0 if code == 200 else 1
            else:
                from app.services.mission_control.runtime_truth import build_runtime_truth

                truth = build_runtime_truth(user_id=uid)
                out = truth.get("runtime_scalability") or {}
            print(json.dumps(out, indent=2, default=str)[:24000])
            return 0

    if args.cmd == "worker-summaries":
        page = int(getattr(args, "page", 1))
        code, body = _req("GET", f"/api/v1/mission-control/runtime/workers/summaries?page={page}", uid=uid)
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "operational":
        if args.operational_cmd == "summary":
            code, body = _req("GET", "/api/v1/mission-control/operational-summary", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.operational_cmd == "trends":
            code, body = _req("GET", "/api/v1/mission-control/runtime/trends", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.operational_cmd == "trajectory":
            code, body = _req("GET", "/api/v1/mission-control/runtime/trajectory", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.operational_cmd == "memory":
            from app.services.mission_control.runtime_truth import build_runtime_truth

            truth = build_runtime_truth(user_id=uid)
            out = {
                "enterprise_operational_memory": truth.get("enterprise_operational_memory"),
                "operational_history_quality": truth.get("operational_history_quality"),
                "continuity_memory": truth.get("continuity_memory"),
            }
            print(json.dumps(out, indent=2, default=str)[:24000])
            return 0

    if args.cmd == "enterprise":
        if args.enterprise_cmd == "overview":
            code, body = _req("GET", "/api/v1/mission-control/executive-overview", uid=uid)
            if code != 200:
                code, body = _req("GET", "/api/v1/mission-control/enterprise/overview", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.enterprise_cmd == "strategy":
            code, body = _req("GET", "/api/v1/mission-control/enterprise/strategy", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.enterprise_cmd == "intelligence":
            code, body = _req("GET", "/api/v1/mission-control/enterprise/intelligence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.enterprise_cmd == "posture":
            code, body = _req("GET", "/api/v1/mission-control/enterprise/posture", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.enterprise_cmd == "memory":
            from app.services.mission_control.runtime_truth import build_runtime_truth

            truth = build_runtime_truth(user_id=uid)
            out = {
                "enterprise_operational_memory": truth.get("enterprise_operational_memory"),
                "operational_history_quality": truth.get("operational_history_quality"),
                "continuity_memory": truth.get("continuity_memory"),
                "runtime_evolution_history": truth.get("runtime_evolution_history"),
            }
            if getattr(args, "json", False):
                print(json.dumps(out, indent=2, default=str)[:24000])
            else:
                print(json.dumps(out, indent=2, default=str)[:24000])
            return 0

    if args.cmd == "automation":
        if args.automation_cmd == "effectiveness":
            code, body = _req("GET", "/api/v1/mission-control/automation/effectiveness", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "intelligence":
        if args.intelligence_cmd == "summary":
            code, body = _req("GET", "/api/v1/mission-control/operational-intelligence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.intelligence_cmd == "risks":
            code, body = _req("GET", "/api/v1/mission-control/governance/risks", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.intelligence_cmd == "recommendations":
            code, body = _req("GET", "/api/v1/mission-control/runtime-recommendations", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "governance":
        if args.governance_cmd == "timeline":
            code, body = _req("GET", "/api/v1/mission-control/governance", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "risks":
            code, body = _req("GET", "/api/v1/mission-control/governance/risks", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "summary":
            code, body = _req("GET", "/api/v1/mission-control/governance/summary", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "trust":
            code, body = _req("GET", "/api/v1/mission-control/governance/trust", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "overview":
            code, body = _req("GET", "/api/v1/mission-control/governance/overview", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "accountability":
            code, body = _req("GET", "/api/v1/mission-control/governance/accountability", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "maturity":
            code, body = _req("GET", "/api/v1/mission-control/governance/maturity", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "progression":
            code, body = _req("GET", "/api/v1/mission-control/governance/progression", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "intelligence":
            code, body = _req("GET", "/api/v1/mission-control/governance/intelligence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "index":
            code, body = _req("GET", "/api/v1/mission-control/governance/index", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "experience":
            code, body = _req("GET", "/api/v1/mission-control/governance-experience", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "search":
            q = urllib.parse.quote(str(getattr(args, "query", "") or ""))
            code, body = _req("GET", f"/api/v1/mission-control/governance/search?q={q}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.governance_cmd == "filter":
            params = []
            for k in ("kind", "actor", "provider"):
                v = getattr(args, k, None)
                if v:
                    params.append(f"{k}={urllib.parse.quote(str(v))}")
            qs = ("?" + "&".join(params)) if params else ""
            code, body = _req("GET", f"/api/v1/mission-control/governance/filter{qs}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "marketplace":
        if args.marketplace_cmd == "packs":
            code, body = _req("GET", "/api/v1/mission-control/automation-packs", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.marketplace_cmd == "run-pack":
            pid = urllib.parse.quote(str(args.pack_id), safe="")
            code, body = _req("POST", f"/api/v1/mission-control/automation-packs/{pid}/run", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.marketplace_cmd == "trust":
            code, body = _req("GET", "/api/v1/mission-control/automation/trust", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "execution":
        if args.execution_cmd == "visibility":
            code, body = _req("GET", "/api/v1/mission-control/execution/visibility", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "workspace":
        if args.workspace_cmd == "summary":
            code, body = _req("GET", "/api/v1/mission-control/workspace-intelligence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workspace_cmd == "risks":
            code, body = _req("GET", "/api/v1/mission-control/workspace-risks", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workspace_cmd == "health":
            code, body = _req("GET", "/api/v1/mission-control/runtime/health", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workspace_cmd == "research-chains":
            q = ""
            if getattr(args, "project_id", None):
                q = f"?project_id={urllib.parse.quote(str(args.project_id))}"
            code, body = _req("GET", f"/api/v1/mission-control/research-chains{q}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "workers":
        if args.workers_cmd == "effectiveness":
            code, body = _req("GET", "/api/v1/mission-control/workers/effectiveness", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "ecosystem":
            code, body = _req("GET", "/api/v1/mission-control/workers/ecosystem", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "coordination":
            code, body = _req("GET", "/api/v1/mission-control/workers/coordination", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "intelligence":
            code, body = _req("GET", "/api/v1/mission-control/workers/intelligence", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "archive":
            code, body = _req("GET", "/api/v1/mission-control/workers/archive", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "lifecycle":
            code, body = _req("GET", "/api/v1/mission-control/workers/lifecycle", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "accountability":
            code, body = _req("GET", "/api/v1/mission-control/workers/accountability", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "overview":
            code, body = _req("GET", "/api/v1/mission-control/workers/overview", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "list":
            code, body = _req("GET", "/api/v1/mission-control/runtime-workers", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "show":
            wid = urllib.parse.quote(str(args.worker_id), safe="")
            code, body = _req("GET", f"/api/v1/mission-control/runtime-workers/{wid}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "deliverables":
            wid = urllib.parse.quote(str(args.worker_id), safe="")
            code, body = _req(
                "GET",
                f"/api/v1/mission-control/runtime-workers/{wid}/deliverables",
                uid=uid,
            )
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.workers_cmd == "continuity":
            wid = urllib.parse.quote(str(args.worker_id), safe="")
            code, body = _req("GET", "/api/v1/mission-control/operator-continuity", uid=uid)
            print(body[:24000])
            code2, body2 = _req(
                "GET",
                f"/api/v1/mission-control/runtime-workers/{wid}/continuations",
                uid=uid,
            )
            if code2 == 200:
                print(body2[:12000])
            return 0 if code == 200 else 1

    if args.cmd == "deliverables":
        if args.deliverables_cmd == "list":
            code, body = _req("GET", "/api/v1/mission-control/deliverables", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deliverables_cmd == "show":
            did = urllib.parse.quote(str(args.deliverable_id), safe="")
            code, body = _req("GET", f"/api/v1/mission-control/deliverables/{did}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deliverables_cmd == "export":
            did = urllib.parse.quote(str(args.deliverable_id), safe="")
            fmt = urllib.parse.quote(str(args.format), safe="")
            code, body = _req(
                "GET",
                f"/api/v1/mission-control/deliverables/{did}/export?format={fmt}",
                uid=uid,
            )
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.deliverables_cmd == "compare":
            from app.services.research_continuity import compare_deliverables

            out = compare_deliverables(str(args.deliverable_id_a), str(args.deliverable_id_b))
            print(json.dumps(out, indent=2, default=str)[:24000])
            return 0 if out.get("ok") else 1

    if args.cmd == "agents":
        if args.agents_cmd == "list":
            code, body = _req("GET", "/api/v1/runtime/agents/", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.agents_cmd == "show":
            aid = urllib.parse.quote(str(args.agent_id), safe="")
            code, body = _req("GET", f"/api/v1/runtime/agents/{aid}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.agents_cmd == "tasks":
            aid = urllib.parse.quote(str(args.agent_id), safe="")
            code, body = _req("GET", f"/api/v1/runtime/agents/{aid}/tasks", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "planning":
        if args.planning_cmd == "list":
            code, body = _req("GET", "/api/v1/runtime/planning", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.planning_cmd == "show":
            pl = urllib.parse.quote(str(args.planning_id), safe="")
            code, body = _req("GET", f"/api/v1/runtime/planning/{pl}", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "optimization":
        subc = getattr(args, "optimization_cmd", None) or "metrics"
        if subc == "metrics":
            code, body = _req("GET", "/api/v1/runtime/optimization", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        print("Unknown optimization subcommand", file=sys.stderr)
        return 1

    if args.cmd == "operations":
        if args.ops_cmd == "list":
            code, body = _req("GET", "/api/v1/operations", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.ops_cmd == "supervisors":
            code, body = _req("GET", "/api/v1/runtime/supervisors", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.ops_cmd == "loops":
            code, body = _req("GET", "/api/v1/runtime/loops", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.ops_cmd == "run":
            payload = json.dumps({"op_type": str(args.op_type), "environment_id": args.environment_id}).encode()
            code, body = _req("POST", "/api/v1/operations/run", uid=uid, body=payload)
            print(body[:24000])
            return 0 if code == 200 else 1

    if args.cmd == "logs":
        from aethos_cli.parity_cli import cmd_logs

        return cmd_logs(lines=int(getattr(args, "log_lines", 80)), category=getattr(args, "log_category", None))

    if args.cmd == "doctor":
        import json
        from app.services.setup.enterprise_setup_doctor import build_enterprise_setup_doctor

        from aethos_cli.parity_cli import cmd_doctor

        ent = build_enterprise_setup_doctor()
        print(json.dumps(ent, indent=2, default=str)[:12000])
        return cmd_doctor(api_base=_base_url())

    if args.cmd == "repair":
        from aethos_cli.runtime_process_cli import cmd_runtime_repair

        return cmd_runtime_repair()

    if args.cmd == "state":
        q = f"?user_id={urllib.parse.quote(args.mission_user)}" if args.mission_user else ""
        code, body = _req("GET", f"/api/v1/mission-control/state{q}", uid=uid)
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "run":
        payload = json.dumps({"text": args.text, "user_id": uid}).encode()
        code, body = _req(
            "POST",
            "/api/v1/mission-control/gateway/run",
            uid=uid,
            body=payload,
        )
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "replay":
        return cmd_replay(uid, args.mission_id)

    if args.cmd == "settings":
        if args.settings_cmd == "get":
            return cmd_settings_get(uid)
        if args.settings_cmd == "set":
            return cmd_settings_set(uid, list(args.pairs))

    if args.cmd == "soul":
        from aethos_cli.soul import soul_dispatch

        av: list[str] = []
        if args.soul_cmd == "add":
            av = [" ".join(args.text)]
        elif args.soul_cmd in ("diff", "rollback"):
            av = [str(args.version)]
        return soul_dispatch(str(args.soul_cmd), uid, av)

    if args.cmd == "skills":
        from app.cli.skills import cmd_skills_install, cmd_skills_list, cmd_skills_remove

        if args.skills_cmd == "list":
            return cmd_skills_list()
        if args.skills_cmd == "install":
            return cmd_skills_install(str(args.name), str(args.source))
        if args.skills_cmd == "remove":
            return cmd_skills_remove(str(args.name))

    if args.cmd == "clawhub":
        from app.cli.clawhub import clawhub_dispatch

        return clawhub_dispatch(args)

    if args.cmd == "plugin":
        from app.cli.plugin import plugin_dispatch

        return plugin_dispatch(args)

    if args.cmd == "scrape":
        from app.cli.scraping import scraping_main

        av = list(args.scrape_argv or [])
        if av and av[0] == "--":
            av = av[1:]
        return scraping_main(av)

    if args.cmd == "cron":
        from app.cli.cron import cron_main

        if args.cron_cmd == "list":
            return cron_main(["list"])
        if args.cron_cmd == "add":
            msg = " ".join(args.message)
            return cron_main(["add", str(args.cron_expression), msg])
        if args.cron_cmd == "remove":
            return cron_main(["remove", str(args.job_id)])
        if args.cron_cmd == "pause":
            return cron_main(["pause", str(args.job_id)])
        if args.cron_cmd == "resume":
            return cron_main(["resume", str(args.job_id)])

    if args.cmd == "dev":
        if args.dev_cmd == "workspace-add":
            return cmd_dev_workspace_add(uid, str(args.name), str(args.repo_path))
        if args.dev_cmd == "run":
            return cmd_dev_run(
                uid,
                workspace_id=str(args.workspace_id),
                goal=str(args.goal),
                agent=args.agent,
                allow_write=bool(args.allow_write),
                allow_commit=bool(args.allow_commit),
                auto_pr=bool(args.auto_pr),
                max_iterations=getattr(args, "max_iterations", None),
            )
        if args.dev_cmd == "schedule":
            return cmd_dev_schedule(
                uid,
                workspace_id=str(args.workspace_id),
                goal=str(args.goal),
                cron=args.cron,
                interval_seconds=args.interval_seconds,
                agent=args.agent,
            )

    if args.cmd == "run-dev":
        print(
            "Use: aethos dev run --workspace <workspace_id> --goal \"…\" [--agent aider]",
            file=sys.stderr,
        )
        return 2

    if args.cmd == "cloud":
        from aethos_cli.cloud_commands import cloud_main

        av2: list[str] = []
        if getattr(args, "cloud_cmd", None) == "list":
            av2 = ["list"]
        elif args.cloud_cmd == "add":
            av2 = [
                "add",
                str(args.name),
                "--deploy-cmd",
                str(args.deploy_cmd),
            ]
            if getattr(args, "pre_deploy", None):
                av2.extend(["--pre-deploy", str(args.pre_deploy)])
            if getattr(args, "login_cmd", None):
                av2.extend(["--login-cmd", str(args.login_cmd)])
            if getattr(args, "login_probe", None):
                av2.extend(["--login-probe", str(args.login_probe)])
            if getattr(args, "url_pattern", None):
                av2.extend(["--url-pattern", str(args.url_pattern)])
            if getattr(args, "deploy_cmd_preview", None):
                av2.extend(["--deploy-cmd-preview", str(args.deploy_cmd_preview)])
        elif args.cloud_cmd == "remove":
            av2 = ["remove", str(args.name)]
        return cloud_main(av2)

    if args.cmd == "setup":
        from aethos_cli.setup_wizard import run_setup_wizard

        sc = getattr(args, "setup_cmd", None)
        if sc == "doctor":
            from aethos_cli.setup_doctor import cmd_setup_doctor

            return cmd_setup_doctor()
        if sc == "validate":
            from aethos_cli.setup_doctor import cmd_setup_validate

            return cmd_setup_validate()
        if sc == "onboarding":
            from aethos_cli.setup_orchestrator_onboarding import run_orchestrator_onboarding

            run_orchestrator_onboarding()
            return 0
        if sc == "certify":
            import json
            from app.services.setup.production_cut_certification import build_production_cut_certification
            from app.services.setup.setup_ready_state_lock import build_setup_ready_state_lock

            out = {
                "ready_state": build_setup_ready_state_lock(),
                **build_production_cut_certification(),
            }
            print(json.dumps(out, indent=2, default=str)[:32000])
            return 0
        if sc == "coverage":
            import json
            from app.services.setup.setup_coverage import build_setup_coverage

            print(json.dumps(build_setup_coverage(), indent=2, default=str)[:24000])
            return 0
        if sc == "status":
            import json
            from app.services.setup.setup_status import build_setup_status
            from aethos_cli.setup_progress_state import build_progress_status

            print(json.dumps({**build_setup_status(), "setup_progress": build_progress_status()}, indent=2, default=str)[:24000])
            return 0
        if sc == "continuity":
            import json
            from app.services.setup.setup_continuity import build_setup_continuity
            from aethos_cli.setup_progress_state import build_progress_status

            print(json.dumps({**build_setup_continuity(), "setup_progress": build_progress_status()}, indent=2, default=str)[:24000])
            return 0
        if sc == "startup":
            from aethos_cli.runtime_launch_cli import cmd_runtime_launch

            return cmd_runtime_launch()
        if sc == "operational-recovery":
            from aethos_cli.runtime_launch_cli import cmd_runtime_startup_recovery

            return cmd_runtime_startup_recovery()
        if sc == "resume":
            from aethos_cli.setup_progress_state import load_setup_progress

            prog = load_setup_progress()
            if prog.get("current_section"):
                print(f"Resuming from section: {prog.get('current_section')}")
            return run_setup_wizard()
        if sc == "first-impression":
            import json
            from app.services.setup.setup_first_impression import build_setup_first_impression

            print(json.dumps(build_setup_first_impression(), indent=2, default=str)[:24000])
            return 0
        if sc == "repair":
            os.environ["NEXA_SETUP_KIND"] = "repair"
            return run_setup_wizard(install_kind="repair")
        return run_setup_wizard()

    if args.cmd == "restart":
        from aethos_cli.restart_cli import cmd_restart

        target = getattr(args, "restart_cmd", None) or "all"
        return cmd_restart(target)

    if args.cmd == "connect":
        from aethos_cli.connection_cli import cmd_connect

        return cmd_connect()

    if args.cmd == "connection":
        from aethos_cli.connection_cli import (
            cmd_connection_diagnose,
            cmd_connection_repair,
            cmd_connection_reset,
            cmd_connection_show,
        )

        if args.connection_cmd == "show":
            return cmd_connection_show()
        if args.connection_cmd == "diagnose":
            return cmd_connection_diagnose()
        if args.connection_cmd == "reset":
            return cmd_connection_reset()
        return cmd_connection_repair()

    if args.cmd == "init-db":
        from aethos_cli.setup_wizard import run_database_setup

        return run_database_setup()

    if args.cmd == "unify-db":
        from aethos_cli.db_migration import unify_databases

        root = _repo_root()
        stats = unify_databases(repo_root=root, extra_env_files=[root / ".env"])
        print(f"Canonical database: {stats['canonical_path']}")
        print(f"Agents (registry table): {stats['agents_in_canonical']}")
        if stats.get("source_path"):
            print(f"Source file used: {stats['source_path']}")
        return 0

    if args.cmd == "migrate-scopes":
        from aethos_cli.agent_commands import run_migrate_scopes

        return run_migrate_scopes(apply=bool(getattr(args, "apply", False)))

    if args.cmd == "configure-bot":
        from aethos_cli.bot_config import configure_bot_env

        return configure_bot_env()

    if args.cmd == "start":
        from aethos_cli.runtime_launch_cli import cmd_runtime_launch

        return cmd_runtime_launch()

    if args.cmd == "stop":
        from aethos_cli.runtime_process_cli import cmd_runtime_stop

        return cmd_runtime_stop()

    if args.cmd == "restart":
        from aethos_cli.runtime_process_cli import cmd_runtime_restart

        return cmd_runtime_restart(clean=False)

    if args.cmd == "status":
        from aethos_cli.cli_status import cmd_status

        return cmd_status()

    if args.cmd == "features":
        from aethos_cli.cli_features import cmd_features

        return cmd_features()

    if args.cmd == "config":
        from aethos_cli.cli_config import cmd_config

        return cmd_config(edit=bool(getattr(args, "edit", False)))

    if args.cmd == "pr":
        from aethos_cli.pr_review import cmd_pr_review

        if args.pr_cmd == "review":
            return cmd_pr_review(str(args.repo), int(args.pr_number))

    if args.cmd == "serve":
        return cmd_serve(str(args.host), int(args.port), bool(args.reload))

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
