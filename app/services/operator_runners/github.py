"""GitHub CLI + git branch diagnostics (read-only)."""

from __future__ import annotations

import subprocess
from typing import Any

from app.services.operator_cli_path import cli_environ_for_operator, which_operator_cli
from app.services.operator_runners.base import evidence_shell, format_operator_progress

_TIMEOUT = 45.0

_GH_MISSING = "`gh` not found in PATH. Run `which gh` in your terminal on this host and retry."


def _gh_bin() -> str | None:
    return which_operator_cli("gh")


def _run_allowlisted(argv: list[str], *, cwd: str | None) -> dict[str, Any]:
    if not argv:
        return {"ok": False, "error": "bad_argv", "stdout": "", "stderr": ""}
    if argv[0] != "gh":
        return {"ok": False, "error": "not_gh", "stdout": "", "stderr": ""}
    if len(argv) < 2 or argv[1].lower() != "auth" or (len(argv) >= 3 and argv[2].lower() != "status"):
        return {"ok": False, "error": "gh_subcommand_not_allowed", "stdout": "", "stderr": ""}
    if not _gh_bin():
        return {"ok": False, "error": "gh_cli_missing", "stdout": "", "stderr": ""}
    env = cli_environ_for_operator()
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
    return body, ev, progress, verified
