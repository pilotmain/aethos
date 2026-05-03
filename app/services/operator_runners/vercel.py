"""Bounded Vercel CLI diagnostics (read-only)."""

from __future__ import annotations

import subprocess
from typing import Any

from app.services.operator_cli_path import cli_environ_for_operator, which_operator_cli
from app.services.operator_runners.base import evidence_shell, format_operator_progress

_TIMEOUT = 60.0

_CLI_MISSING = (
    "`vercel` not found in PATH. Run `which vercel` in your terminal on this host and retry."
)


def _vercel_bin() -> str | None:
    return which_operator_cli("vercel")


def _run_vercel_allowlisted(argv: list[str], *, cwd: str | None) -> dict[str, Any]:
    if not argv or argv[0] != "vercel":
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
    if not _vercel_bin():
        return {"ok": False, "error": "vercel_cli_missing", "stdout": "", "stderr": ""}
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
    return body, ev, progress, verified
