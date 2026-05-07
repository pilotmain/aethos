"""CLI entrypoint: ``python -m aethos_cli`` — AethOS HTTP API client (Phase 21)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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

    sub.add_parser("run-dev", help="Deprecated alias; use: nexa dev run …")

    sp_setup = sub.add_parser(
        "setup",
        help="Interactive native setup wizard (writes .env keys; see docs/NATIVE_SETUP.md)",
    )

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
        and args.cmd in ("serve", "setup", "init-db", "unify-db", "migrate-scopes")
    ):
        from aethos_cli.banner import maybe_print_sponsor_hint, print_banner, should_show_banner

        if should_show_banner():
            print_banner()
            maybe_print_sponsor_hint()

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
