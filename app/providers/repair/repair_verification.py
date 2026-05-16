# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace verification before provider redeploy (Phase 2 Step 6)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.providers.actions.provider_logs import summarize_cli_streams
from app.providers.repair.failure_classification import classify_failure_text


_ALLOWED_PREFIXES = ("npm ", "node ", "python ", "python3 ", "pytest ", "pnpm ", "yarn ")


def _run_shell(command: str, cwd: Path, *, timeout_sec: float = 300.0) -> dict[str, Any]:
    low = command.strip().lower()
    if not any(low.startswith(p) for p in _ALLOWED_PREFIXES):
        return {"ok": False, "error": "command_not_allowed", "command": command}
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=max(10.0, timeout_sec),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "command": command}
    summ = summarize_cli_streams(returncode=int(proc.returncode or 0), stdout=proc.stdout or "", stderr=proc.stderr or "")
    ok = int(proc.returncode or 0) == 0
    return {
        "ok": ok,
        "command": command,
        "returncode": proc.returncode,
        "failure_category": None if ok else classify_failure_text((proc.stderr or "") + (proc.stdout or "")),
        "cli": summ,
    }


def run_verification_suite(repo_path: str | Path) -> dict[str, Any]:
    """Run test → build → lint from package.json when present."""
    repo = Path(repo_path).resolve()
    pkg = repo / "package.json"
    commands: list[str] = []
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = (data.get("scripts") or {}) if isinstance(data, dict) else {}
            if isinstance(scripts, dict):
                for name in ("test", "build", "lint"):
                    if name in scripts:
                        commands.append(f"npm run {name}")
        except (OSError, json.JSONDecodeError):
            pass
    if not commands and pkg.is_file():
        commands.append("npm run build")
    if not commands and (repo / "pyproject.toml").is_file():
        commands.append("python -m compileall -q .")
    results: list[dict[str, Any]] = []
    for cmd in commands:
        row = _run_shell(cmd, repo)
        results.append(row)
        if not row.get("ok"):
            return {"ok": False, "results": results, "failed_command": cmd}
    if not results:
        return {"ok": True, "results": [], "note": "no_verification_commands"}
    return {"ok": True, "results": results}


def build_verification_result(suite: dict[str, Any], *, blocked_redeploy: bool = False) -> dict[str, Any]:
    """Operator-facing verification summary (Phase 2 Step 7)."""
    commands: list[dict[str, Any]] = []
    for row in suite.get("results") or []:
        if not isinstance(row, dict):
            continue
        cli = row.get("cli") if isinstance(row.get("cli"), dict) else {}
        commands.append(
            {
                "command": row.get("command"),
                "returncode": row.get("returncode"),
                "stdout_preview": (cli.get("stdout_preview") or cli.get("preview") or "")[:500],
                "stderr_preview": (cli.get("stderr_preview") or "")[:500],
            }
        )
    verified = bool(suite.get("ok"))
    return {
        "verified": verified,
        "commands": commands,
        "blocked_redeploy": blocked_redeploy or not verified,
        "failed_command": suite.get("failed_command"),
    }
