# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Preflight checks before the host runs the dev agent (git, aider, paths, API keys, notify)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.services.handoff_paths import PROJECT_ROOT


def _ok(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": (detail or "")[:2000]}


def check_command(cmd: str) -> dict:
    path = shutil.which(cmd)
    if path:
        return _ok(f"command:{cmd}", True, path)
    return _ok(f"command:{cmd}", False, f"`{cmd}` not found on PATH")


def check_agent_tasks_writable(root: Path) -> dict:
    try:
        p = root / ".agent_tasks"
        p.mkdir(parents=True, exist_ok=True)
        t = p / ".preflight_write_test"
        t.write_text("ok", encoding="utf-8")
        t.unlink()
        return _ok(".agent_tasks", True, str(p))
    except OSError as e:
        return _ok(".agent_tasks", False, str(e)[:2000])


def check_git_repo(project_root: Path) -> dict:
    import subprocess

    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(project_root),
        text=True,
        capture_output=True,
    )
    if r.returncode == 0 and (r.stdout or "").strip() == "true":
        return _ok("git work tree", True)
    return _ok("git work tree", False, (r.stderr or r.stdout or "not a repo")[:1000])


def check_test_command() -> dict:
    raw = (os.getenv("DEV_AGENT_TEST_COMMAND") or "python -m pytest").strip()
    if not raw or raw.startswith("#"):
        return _ok("DEV_AGENT_TEST_COMMAND", False, "unset or empty")
    return _ok("DEV_AGENT_TEST_COMMAND", True, raw[:200])


def check_notification_config() -> dict:
    s = get_settings()
    on = (os.getenv("DEV_WORKER_TELEGRAM_NOTIFY", "true") or "true").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }
    if not on:
        return _ok("telegram notify (DEV_WORKER_TELEGRAM_NOTIFY)", True, "notify disabled (OK for headless runs)")
    if not s.telegram_bot_token:
        return _ok("telegram token", False, "TELEGRAM_BOT_TOKEN not set; notifications need a bot token in settings")
    return _ok("telegram token", True, "set")


def check_api_key_present() -> dict:
    s = get_settings()
    has = bool(
        (s.anthropic_api_key or "").strip()
        or (s.openai_api_key or "").strip()
        or (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        or (os.getenv("OPENAI_API_KEY") or "").strip()
    )
    if has:
        return _ok("llm API keys (settings or env)", True, "at least one present")
    return _ok(
        "llm API keys (settings or env)",
        False,
        "set ANTHROPIC_API_KEY / OPENAI_API_KEY or .env (required for most aider runs)",
    )


def run_dev_preflight(project_root: Path | None = None) -> dict:
    pr = project_root or Path(PROJECT_ROOT)
    checks: list[dict] = [
        check_command("git"),
        check_command("aider"),
        check_agent_tasks_writable(pr),
        check_git_repo(pr),
        check_test_command(),
        check_api_key_present(),
        check_notification_config(),
    ]
    ok = all(c.get("ok") for c in checks)
    return {"ok": bool(ok), "checks": checks}


def format_preflight_errors(pref: dict) -> str:
    lines: list[str] = []
    for c in (pref or {}).get("checks") or []:
        if not c.get("ok"):
            lines.append(f"- {c.get('name')}: {c.get('detail', '')[:500]}")
    if not lines:
        return "Preflight had issues (see preflight.json)."
    return "Preflight failed:\n" + "\n".join(lines)


def write_preflight_json(artifact_dir: Path, preflight: dict) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    p = artifact_dir / "preflight.json"
    p.write_text(json.dumps(preflight, indent=2)[:200_000], encoding="utf-8")
    return p
