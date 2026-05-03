"""
Phase 58 — bounded Railway + workspace investigation after prefs are captured.

Runs only allowlisted local checks. Never deploys, never narrates success without
real command output attached to this turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.dev_runtime.executor import run_dev_command
from app.services.dev_runtime.workspace import list_workspaces
from app.services.integrations.railway.cli import railway_binary_on_path, run_railway_cli


def _truncate(s: str, limit: int = 6000) -> str:
    t = (s or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 40] + "\n… (truncated)"


@dataclass
class BoundedRailwayInvestigation:
    """Evidence captured this turn (never implies deploy performed)."""

    skipped_reason: str | None = None
    workspace_paths: list[str] = field(default_factory=list)
    railway_cli_present: bool = False
    railway_whoami: dict | None = None
    railway_status: dict | None = None
    railway_logs: dict | None = None
    git_status: dict | None = None
    deploy_blocked_by_policy: bool = True
    policy_note: str = ""

    def any_command_ok(self) -> bool:
        for r in (self.railway_whoami, self.railway_status, self.railway_logs):
            if isinstance(r, dict) and r.get("ok"):
                return True
        if isinstance(self.git_status, dict) and self.git_status.get("ok"):
            return True
        return False


def _deploy_policy_note(collected: dict[str, object]) -> tuple[bool, str]:
    mode = str(collected.get("deploy_mode") or "").strip()
    if mode == "deploy_when_ready":
        return (
            False,
            "_Deploy is **not** triggered automatically. Say explicitly that you approve deploy after reviewing findings._",
        )
    return (
        True,
        "_Deploy remains **blocked** until you approve — findings below are diagnostic only._",
    )


def run_bounded_railway_repo_investigation(
    db: Session,
    user_id: str,
    collected: dict[str, object],
) -> BoundedRailwayInvestigation:
    out = BoundedRailwayInvestigation()
    blocked, note = _deploy_policy_note(collected)
    out.deploy_blocked_by_policy = blocked
    out.policy_note = note

    s = get_settings()
    if not getattr(s, "nexa_external_execution_runner_enabled", True):
        out.skipped_reason = "runner_disabled"
        return out
    if not bool(getattr(s, "nexa_host_executor_enabled", False)):
        out.skipped_reason = "host_executor_disabled"
        return out

    uid = (user_id or "").strip()
    if not uid:
        out.skipped_reason = "no_user"
        return out

    try:
        rows = list_workspaces(db, uid)
    except Exception:
        rows = []
    paths = [str(getattr(r, "repo_path", "") or "").strip() for r in rows]
    paths = [p for p in paths if p]
    out.workspace_paths = paths

    if not paths:
        out.skipped_reason = "no_workspace"
        return out

    repo_root = paths[0]
    if len(paths) > 1:
        # Still investigate primary workspace; caller surfaces ambiguity in copy.
        pass

    root_path = Path(repo_root)
    if not root_path.is_dir():
        out.skipped_reason = "workspace_path_missing"
        return out

    cwd = str(root_path.resolve())
    out.railway_cli_present = railway_binary_on_path()

    auth = str(collected.get("auth_method") or "").strip()
    if auth == "local_cli" and not out.railway_cli_present:
        out.railway_whoami = {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "error": "railway_cli_missing_for_local_cli_pref",
        }
    elif not out.railway_cli_present:
        out.railway_whoami = {"ok": False, "stdout": "", "stderr": "", "error": "railway_cli_missing"}
    else:
        out.railway_whoami = run_railway_cli("whoami", [], cwd=cwd, timeout=30.0)

    if out.railway_cli_present:
        out.railway_status = run_railway_cli("status", [], cwd=cwd, timeout=40.0)
        logs = run_railway_cli("logs", ["--tail", "100"], cwd=cwd, timeout=55.0)
        if isinstance(logs, dict) and not logs.get("ok") and logs.get("error") != "railway_cli_missing":
            logs = run_railway_cli("logs", [], cwd=cwd, timeout=55.0)
        out.railway_logs = logs

    out.git_status = run_dev_command(cwd, "git status")

    return out


def format_investigation_for_chat(result: BoundedRailwayInvestigation) -> str:
    """User-facing block with verified snippets only."""
    lines: list[str] = [
        "### Verified checks (this host)",
        "",
    ]

    if result.skipped_reason:
        reasons = {
            "runner_disabled": "External execution runner is disabled (`NEXA_EXTERNAL_EXECUTION_RUNNER_ENABLED`).",
            "host_executor_disabled": "Host executor is off (`NEXA_HOST_EXECUTOR_ENABLED`) — no local workspace commands ran.",
            "no_workspace": "No dev workspace is registered — register a repo path under Mission Control → Dev.",
            "no_user": "Missing user id for workspace lookup.",
            "workspace_path_missing": "Registered workspace path is not a directory on this host.",
        }
        lines.append(reasons.get(result.skipped_reason, f"Skipped ({result.skipped_reason})."))
        lines.append("")
        lines.append(result.policy_note)
        return "\n".join(lines).strip()

    if len(result.workspace_paths) > 1:
        lines.append(
            f"_Multiple workspaces registered — using **{result.workspace_paths[0]}** first. "
            "Narrow to one in Mission Control for deterministic Railway linkage._"
        )
        lines.append("")

    def _emit_cmd(title: str, block: dict | None) -> None:
        if not isinstance(block, dict):
            return
        lines.append(f"**{title}**")
        if block.get("error"):
            lines.append(f"- error: `{block['error']}`")
        ok = bool(block.get("ok"))
        lines.append(f"- exit: **{'ok' if ok else 'failed'}**")
        stdout = _truncate(str(block.get("stdout") or ""), 4000)
        stderr = _truncate(str(block.get("stderr") or ""), 2500)
        if stdout:
            lines.append("")
            lines.append("```")
            lines.append(stdout)
            lines.append("```")
        if stderr:
            lines.append("")
            lines.append("stderr:")
            lines.append("```")
            lines.append(stderr)
            lines.append("```")
        lines.append("")

    _emit_cmd("`railway whoami`", result.railway_whoami)
    _emit_cmd("`railway status`", result.railway_status)
    _emit_cmd("`railway logs` (tail)", result.railway_logs)

    gs = result.git_status
    if isinstance(gs, dict):
        lines.append("**`git status`** (allowlisted)")
        lines.append(f"- exit: **{'ok' if gs.get('ok') else 'failed'}**")
        so = _truncate(str(gs.get("stdout") or ""), 3000)
        if so:
            lines.append("")
            lines.append("```")
            lines.append(so)
            lines.append("```")
        lines.append("")

    lines.append(result.policy_note)
    lines.append("")
    lines.append(
        "_No deploy or redeploy was run. Railway output above is exactly what the CLI returned on this worker._"
    )
    return "\n".join(lines).strip()


__all__ = [
    "BoundedRailwayInvestigation",
    "format_investigation_for_chat",
    "run_bounded_railway_repo_investigation",
]
