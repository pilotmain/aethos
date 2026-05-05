"""CLI entrypoint: ``python -m nexa_cli`` — Nexa Next HTTP API client (Phase 21)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _base_url() -> str:
    return (os.environ.get("NEXA_API_BASE") or "http://127.0.0.1:8000").rstrip("/")


def _headers(uid: str) -> dict[str, str]:
    h = {"X-User-Id": uid, "Accept": "application/json"}
    tok = (os.environ.get("NEXA_WEB_API_TOKEN") or "").strip()
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
    p = argparse.ArgumentParser(prog="nexa", description="Nexa Next CLI (HTTP)")
    p.add_argument(
        "--user-id",
        default=os.environ.get("NEXA_CLI_USER_ID") or "cli_user",
        help="X-User-Id header (or env NEXA_CLI_USER_ID)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

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

    sub.add_parser("run-dev", help="Deprecated alias; use: nexa dev run …")


    sp_pr = sub.add_parser(
        "pr",
        help="Automated GitHub PR review (requires GITHUB_TOKEN + NEXA_PR_REVIEW_ENABLED)",
    )
    pr_sub = sp_pr.add_subparsers(dest="pr_cmd", required=True)
    sp_prev = pr_sub.add_parser("review", help="Analyze PR and post GitHub review")
    sp_prev.add_argument("repo", help="owner/repo")
    sp_prev.add_argument("pr_number", type=int)

    args = p.parse_args()
    uid = str(args.user_id)

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


    if args.cmd == "pr":
        from nexa_cli.pr_review import cmd_pr_review

        if args.pr_cmd == "review":
            return cmd_pr_review(str(args.repo), int(args.pr_number))

    if args.cmd == "run-dev":
        print(
            "Use: nexa dev run --workspace <workspace_id> --goal \"…\" [--agent aider]",
            file=sys.stderr,
        )
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
