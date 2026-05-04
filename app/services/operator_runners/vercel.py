"""Bounded Vercel CLI diagnostics (read-only)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback, operator_cli_argv_resolves
from app.services.operator_cli_path import cli_environ_for_operator
from app.services.operator_runners.base import evidence_shell, format_operator_progress
from app.services.operator_auth_guidance import append_guidance_if_needed_vercel
from app.services.operator_shell_cli import profile_shell_enabled, run_allowlisted_argv_via_login_shell

_TIMEOUT = 60.0

_CLI_MISSING = (
    "`vercel` not found in PATH. Run `which vercel` in your terminal on this host and retry."
)


def _run_vercel_allowlisted(argv: list[str], *, cwd: str | None) -> dict[str, Any]:
    argv = apply_operator_cli_absolute_fallback(list(argv))
    if not argv or Path(argv[0]).name != "vercel":
        return {"ok": False, "error": "bad_argv", "stdout": "", "stderr": ""}
    if len(argv) < 2:
        return {"ok": False, "error": "missing_subcommand", "stdout": "", "stderr": ""}
    sub = argv[1].lower()
    tail = [x.lower() for x in argv[2:]]
    allowed_whoami = len(argv) == 2 and sub == "whoami"
    allowed_project_ls = sub == "project" and tail == ["ls"]
    allowed_projects = sub == "projects" and tail in ([], ["ls"])
    if not (allowed_whoami or allowed_project_ls or allowed_projects):
        return {"ok": False, "error": "vercel_subcommand_not_allowed", "stdout": "", "stderr": ""}
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
        return {"ok": False, "error": "vercel_cli_missing", "stdout": "", "stderr": ""}
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


def run_vercel_operator_readonly(*, cwd: str | None = None) -> tuple[str, dict[str, Any], list[str], bool]:
    """
    Run allowlisted ``vercel`` commands; return markdown body, evidence, progress lines, verified probe.

    ``verified`` True when ``vercel whoami`` exits zero with output.
    """
    progress: list[str] = [
        "Starting Vercel investigation",
        "Checking CLI availability",
    ]
    cmds: list[dict[str, Any]] = []

    whoami = _run_vercel_allowlisted(["vercel", "whoami"], cwd=cwd)
    cmds.append({"argv": ["vercel", "whoami"], "result": whoami})
    progress.append("Running `vercel whoami`")

    proj = _run_vercel_allowlisted(["vercel", "project", "ls"], cwd=cwd)
    argv_proj = ["vercel", "project", "ls"]
    if not proj.get("ok") and proj.get("error") != "vercel_cli_missing":
        proj = _run_vercel_allowlisted(["vercel", "projects"], cwd=cwd)
        argv_proj = ["vercel", "projects"]
    cmds.append({"argv": argv_proj, "result": proj})
    progress.append(f"Running `{' '.join(argv_proj)}`")

    ev = evidence_shell(provider="vercel", commands=cmds, workspace_path=cwd)

    lines: list[str] = [format_operator_progress(progress), "", "### CLI output", ""]
    verified = bool(whoami.get("ok") and (whoami.get("stdout") or "").strip())

    if whoami.get("error") == "vercel_cli_missing":
        lines.append(_CLI_MISSING)
    else:
        lines.append("**vercel whoami**")
        if whoami.get("stderr"):
            lines.extend(["```", whoami["stderr"][:4000], "```"])
        if whoami.get("stdout"):
            lines.extend(["```", whoami["stdout"][:6000], "```"])

    lines.append("")
    lines.append("**project list**")
    if proj.get("error") == "vercel_cli_missing":
        lines.append("_Skipped — Vercel CLI missing._")
    else:
        if proj.get("stderr"):
            lines.extend(["```", proj["stderr"][:4000], "```"])
        if proj.get("stdout"):
            lines.extend(["```", proj["stdout"][:6000], "```"])

    body = "\n".join(lines).strip()
    body += "\n\n_Read-only diagnostics — no deploy or git write from this step._"
    body = append_guidance_if_needed_vercel(body, whoami)
    return body, ev, progress, verified
