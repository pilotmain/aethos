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
        help="First-time operator onboarding (OpenClaw-class; same as: aethos setup)",
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

    sp_message = sub.add_parser("message", help="Gateway message dispatch (OpenClaw-class)")
    msg_sub = sp_message.add_subparsers(dest="message_cmd", required=True)
    sp_msg_send = msg_sub.add_parser("send", help="POST mission-control/gateway/run")
    sp_msg_send.add_argument("text", help="User message body")
    sp_msg_send.add_argument(
        "--workflow",
        action="store_true",
        help="Enqueue persistent tool workflow (OpenClaw parity) instead of chat.",
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

    sp_task = sub.add_parser("task", help="Runtime workflow task inspection (OpenClaw parity)")
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

    sp_dep = sub.add_parser("deployments", help="Deployment runtime API (OpenClaw infra parity)")
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

    sp_env = sub.add_parser("environments", help="Environment runtime API (OpenClaw infra parity)")
    env_sub = sp_env.add_subparsers(dest="env_cmd", required=True)
    env_sub.add_parser("list", help="GET /api/v1/environments")
    env_sub.add_parser("locks", help="GET /api/v1/environments/locks")
    sp_env_show = env_sub.add_parser("show", help="GET /api/v1/environments/{id}")
    sp_env_show.add_argument("environment_id")

    sp_runtime = sub.add_parser("runtime", help="Unified runtime cohesion (Phase 3 Step 11–12)")
    rt_sub = sp_runtime.add_subparsers(dest="runtime_cmd", required=True)
    rt_sub.add_parser("health", help="GET /api/v1/mission-control/runtime/health")
    rt_sub.add_parser("timeline", help="GET /api/v1/mission-control/runtime/timeline")
    rt_sub.add_parser("recommendations", help="GET /api/v1/mission-control/runtime-recommendations")
    rt_sub.add_parser("workers", help="GET /api/v1/mission-control/runtime-workers")
    rt_sub.add_parser("performance", help="GET /api/v1/mission-control/runtime/performance")
    rt_sub.add_parser("cache", help="Hydration cache metrics from runtime state")
    rt_sub.add_parser("hydration", help="Incremental hydration metrics")
    rt_sub.add_parser("latency", help="Operational responsiveness summary")
    rt_sub.add_parser("scalability", help="Runtime scalability bounds summary")

    sp_opsum = sub.add_parser("operational", help="Operational summary (Phase 3 Step 11)")
    op_sub = sp_opsum.add_subparsers(dest="operational_cmd", required=True)
    op_sub.add_parser("summary", help="GET /api/v1/mission-control/operational-summary")

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

    sp_mkt = sub.add_parser("marketplace", help="Marketplace automation packs")
    mkt_sub = sp_mkt.add_subparsers(dest="marketplace_cmd", required=True)
    mkt_sub.add_parser("packs", help="GET /api/v1/mission-control/automation-packs")
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

    sp_planning = sub.add_parser("planning", help="Adaptive planning runtime API (OpenClaw parity)")
    plan_sub = sp_planning.add_subparsers(dest="planning_cmd", required=True)
    plan_sub.add_parser("list", help="GET /api/v1/runtime/planning")
    sp_plan_show = plan_sub.add_parser("show", help="GET /api/v1/runtime/planning/{planning_id}")
    sp_plan_show.add_argument("planning_id")

    sp_optimization = sub.add_parser(
        "optimization",
        help="Runtime optimization snapshot (OpenClaw parity; default: metrics)",
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
        help="Diagnostics: compileall + optional API health (OpenClaw-class)",
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
    sk_ins = sk_sub.add_parser("install", help="Install skill (ClawHub / file / URL)")
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
        # `app` not on PYTHONPATH (minimal install / wrong CWD) — skip ClawHub subcommands.
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
        help="Interactive native setup wizard (writes .env keys; see docs/NATIVE_SETUP.md)",
    )

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
        if args.runtime_cmd == "health":
            code, body = _req("GET", "/api/v1/mission-control/runtime/health", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
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
            code, body = _req("GET", "/api/v1/mission-control/runtime/performance", uid=uid)
            print(body[:24000])
            return 0 if code == 200 else 1
        if args.runtime_cmd in ("cache", "hydration", "latency", "scalability"):
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
            elif args.runtime_cmd == "hydration":
                out = h
            elif args.runtime_cmd == "latency":
                out = {
                    "last_hydration_ms": h.get("last_hydration_ms"),
                    "last_truth_build_ms": disc.get("last_truth_build_ms"),
                    "target_cached_read_ms": 500,
                }
            else:
                from app.services.mission_control.runtime_truth import build_runtime_truth

                truth = build_runtime_truth(user_id=uid)
                out = truth.get("runtime_scalability") or {}
            print(json.dumps(out, indent=2, default=str)[:24000])
            return 0

    if args.cmd == "operational":
        if args.operational_cmd == "summary":
            code, body = _req("GET", "/api/v1/mission-control/operational-summary", uid=uid)
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
        from aethos_cli.parity_cli import cmd_doctor

        return cmd_doctor(api_base=_base_url())

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

        return run_setup_wizard()

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
