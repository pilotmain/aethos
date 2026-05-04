"""GitHub CLI + git branch diagnostics (read-only)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback, operator_cli_argv_resolves
from app.services.operator_cli_path import cli_environ_for_operator
from app.services.operator_runners.base import evidence_shell, format_operator_progress
from app.services.operator_auth_guidance import append_guidance_if_needed_github
from app.services.operator_verify_followup import append_verify_vs_mutate_followup
from app.services.operator_shell_cli import profile_shell_enabled, run_allowlisted_argv_via_login_shell

_TIMEOUT = 45.0

_GH_MISSING = "`gh` not found in PATH. Run `which gh` in your terminal on this host and retry."


def _run_allowlisted(argv: list[str], *, cwd: str | None) -> dict[str, Any]:
    argv = apply_operator_cli_absolute_fallback(list(argv))
    if not argv:
        return {"ok": False, "error": "bad_argv", "stdout": "", "stderr": ""}
    if Path(argv[0]).name != "gh":
        return {"ok": False, "error": "not_gh", "stdout": "", "stderr": ""}
    if len(argv) < 2 or argv[1].lower() != "auth" or (len(argv) >= 3 and argv[2].lower() != "status"):
        return {"ok": False, "error": "gh_subcommand_not_allowed", "stdout": "", "stderr": ""}
    env = cli_environ_for_operator()
    if profile_shell_enabled():
        r = run_allowlisted_argv_via_login_shell(
            argv,
            cwd=cwd if cwd is not None else os.getcwd(),
            timeout=_TIMEOUT,
            env=env,
        )
        if r.get("error"):
            if r.get("error") == "timeout":
                return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
            return {
                "ok": False,
                "error": str(r.get("error")),
                "stdout": (r.get("stdout") or "").strip(),
                "stderr": (r.get("stderr") or "").strip(),
            }
        return {
            "ok": bool(r.get("ok")),
            "exit_code": int(r.get("exit_code") or 0),
            "stdout": (r.get("stdout") or "").strip(),
            "stderr": (r.get("stderr") or "").strip(),
        }
    if not operator_cli_argv_resolves(argv):
        return {"ok": False, "error": "gh_cli_missing", "stdout": "", "stderr": ""}
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": ""}


def run_github_operator_readonly(*, cwd: str | None = None) -> tuple[str, dict[str, Any], list[str], bool]:
    progress = ["Starting GitHub CLI check", "Running `gh auth status`"]
    auth = _run_allowlisted(["gh", "auth", "status"], cwd=cwd)
    cmds = [{"argv": ["gh", "auth", "status"], "result": auth}]
    ev = evidence_shell(provider="github", commands=cmds, workspace_path=cwd)

    lines: list[str] = [format_operator_progress(progress), "", "### gh auth status", ""]
    verified = bool(auth.get("ok"))
    if auth.get("error") == "gh_cli_missing":
        lines.append(_GH_MISSING)
    elif auth.get("stdout"):
        lines.append("```")
        lines.append(auth["stdout"][:6000])
        lines.append("```")
    if auth.get("stderr"):
        lines.append("```")
        lines.append(auth["stderr"][:4000])
        lines.append("```")

    body = "\n".join(lines).strip()
    body += "\n\n_Read-only — no PR or push performed._"
    body = append_guidance_if_needed_github(body, auth)
    body = append_verify_vs_mutate_followup(body, verified=verified, provider_label="GitHub CLI (`gh`)")
    return body, ev, progress, verified
