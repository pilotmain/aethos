"""
Phase 58 — bounded Railway + workspace investigation after prefs are captured.

Runs only allowlisted local checks. Never deploys, never narrates success without
real command output attached to this turn.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.dev_runtime.executor import run_dev_command
from app.services.dev_runtime.workspace import list_workspaces
from app.services.events.envelope import emit_runtime_event
from app.services.integrations.railway.cli import railway_binary_on_path, run_railway_cli

_log = logging.getLogger(__name__)


def _operator_zero_nag() -> bool:
    try:
        s = get_settings()
        return bool(getattr(s, "nexa_operator_mode", False)) and bool(getattr(s, "nexa_operator_zero_nag", True))
    except Exception:  # noqa: BLE001
        return False


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
    railway_env_token_present: bool = False
    railway_cli_present: bool = False
    railway_whoami: dict | None = None
    railway_status: dict | None = None
    railway_logs: dict | None = None
    git_status: dict | None = None
    deploy_blocked_by_policy: bool = True
    policy_note: str = ""
    progress_lines: list[str] = field(default_factory=list)

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


def _emit_progress_step(
    inv: BoundedRailwayInvestigation,
    label: str,
    *,
    on_progress: Callable[[dict[str, Any]], None] | None,
    progress_user_id: str | None,
    emit_bus: bool,
) -> None:
    inv.progress_lines.append(label)
    if on_progress is not None:
        try:
            on_progress({"type": "progress", "label": label})
        except Exception:
            pass
    uid = (progress_user_id or "").strip()
    if emit_bus and uid:
        emit_runtime_event(
            "external_execution.progress",
            user_id=uid,
            payload={"label": label},
        )


def _log_bounded_runner_done(uid: str, inv: BoundedRailwayInvestigation) -> None:
    """Mandatory observability for bounded Railway probes (retry / resume / direct)."""
    executed = inv.skipped_reason is None
    _log.info(
        "RUNNER_BOUNDED user_id=%s executed=%s skipped_reason=%s railway_cli=%s railway_token_env=%s "
        "workspace_count=%s",
        uid or None,
        executed,
        inv.skipped_reason,
        inv.railway_cli_present,
        inv.railway_env_token_present,
        len(inv.workspace_paths),
    )


def run_bounded_railway_repo_investigation(
    db: Session,
    user_id: str,
    collected: dict[str, object],
    *,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    progress_user_id: str | None = None,
    emit_progress_events: bool = True,
) -> BoundedRailwayInvestigation:
    uid = (user_id or "").strip()
    bus_uid = (progress_user_id or uid).strip() or None

    def _step(label: str) -> None:
        _emit_progress_step(
            out,
            label,
            on_progress=on_progress,
            progress_user_id=bus_uid,
            emit_bus=emit_progress_events,
        )

    out = BoundedRailwayInvestigation()
    _step("Starting investigation")
    out.railway_env_token_present = bool(
        (os.environ.get("RAILWAY_TOKEN") or "").strip()
        or (os.environ.get("RAILWAY_API_TOKEN") or "").strip()
    )
    _step("Checking Railway auth")
    blocked, note = _deploy_policy_note(collected)
    out.deploy_blocked_by_policy = blocked
    out.policy_note = note

    s = get_settings()
    _step("Checking runner configuration")
    if not getattr(s, "nexa_external_execution_runner_enabled", True):
        out.skipped_reason = "runner_disabled"
        _step("Stopped: external execution runner is disabled on this host")
        _log_bounded_runner_done(uid, out)
        return out
    _step("Checking host executor configuration")
    if not bool(getattr(s, "nexa_host_executor_enabled", False)):
        out.skipped_reason = "host_executor_disabled"
        _step("Stopped: host executor disabled (`NEXA_HOST_EXECUTOR_ENABLED`)")
        _log_bounded_runner_done(uid, out)
        return out

    if not uid:
        out.skipped_reason = "no_user"
        _step("Stopped: missing user id for workspace lookup")
        _log_bounded_runner_done(uid, out)
        return out

    _step("Resolving registered dev workspace")
    try:
        rows = list_workspaces(db, uid)
    except Exception:
        rows = []
    paths = [str(getattr(r, "repo_path", "") or "").strip() for r in rows]
    paths = [p for p in paths if p]
    out.workspace_paths = paths

    if not paths:
        out.skipped_reason = "no_workspace"
        _step("Stopped: no dev workspace registered for this user")
        _log_bounded_runner_done(uid, out)
        return out

    repo_root = paths[0]
    if len(paths) > 1:
        # Still investigate primary workspace; caller surfaces ambiguity in copy.
        pass

    root_path = Path(repo_root)
    if not root_path.is_dir():
        out.skipped_reason = "workspace_path_missing"
        _step("Stopped: workspace path is not a directory on this host")
        _log_bounded_runner_done(uid, out)
        return out

    cwd = str(root_path.resolve())
    _step("Checking Railway CLI availability")
    out.railway_cli_present = railway_binary_on_path()

    auth = str(collected.get("auth_method") or "").strip()
    _step("Running railway whoami")
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
        _step("Running railway status")
        out.railway_status = run_railway_cli("status", [], cwd=cwd, timeout=40.0)
        _step("Fetching logs")
        logs = run_railway_cli("logs", ["--tail", "100"], cwd=cwd, timeout=55.0)
        if isinstance(logs, dict) and not logs.get("ok") and logs.get("error") != "railway_cli_missing":
            logs = run_railway_cli("logs", [], cwd=cwd, timeout=55.0)
        out.railway_logs = logs

    _step("Inspecting repo")
    out.git_status = run_dev_command(cwd, "git status")

    _step("Preparing findings")
    _log_bounded_runner_done(uid, out)
    return out


def investigation_to_public_payload(inv: BoundedRailwayInvestigation) -> dict[str, Any]:
    """Structured blocker for APIs — ``ran`` is False when no workspace/executor/cli path ran."""
    if inv.skipped_reason:
        return {"ran": False, "reason": inv.skipped_reason}
    return {"ran": True, "reason": None}


def _format_progress_preamble(inv: BoundedRailwayInvestigation) -> str:
    if not inv.progress_lines:
        return ""
    body = "\n".join(f"- {x}" for x in inv.progress_lines)
    return f"### Progress\n\n{body}\n\n---\n\n"


def analyze_investigation_for_contract(inv: BoundedRailwayInvestigation) -> dict[str, Any]:
    """Structured facts from captured CLI output — no LLM (honest checkmarks)."""

    def _ok(block: dict | None) -> bool:
        return isinstance(block, dict) and bool(block.get("ok"))

    if inv.skipped_reason:
        return {
            "blocked": True,
            "blocker": inv.skipped_reason,
            "whoami_ok": False,
            "status_ok": False,
            "logs_ok": False,
            "git_ok": False,
        }
    return {
        "blocked": False,
        "blocker": None,
        "whoami_ok": _ok(inv.railway_whoami),
        "status_ok": _ok(inv.railway_status),
        "logs_ok": _ok(inv.railway_logs),
        "git_ok": _ok(inv.git_status),
        "cli_present": inv.railway_cli_present,
        "token_env_present": inv.railway_env_token_present,
    }


def format_execution_summary_contract(inv: BoundedRailwayInvestigation) -> str:
    """Terminal summary — ✔/✖ tied to real command outcomes only."""
    analysis = analyze_investigation_for_contract(inv)
    lines: list[str] = ["### Summary", ""]
    if analysis["blocked"]:
        lines.append(f"- ✖ **Run blocked:** `{analysis['blocker']}`")
        lines.append("")
        if _operator_zero_nag():
            lines.append("_See **Progress** above. Say **retry external execution** after wiring this worker._")
            lines.append("")
            lines.append("_No deploy or push was attempted._")
            return "\n".join(lines).strip()
        lines.append(
            "**Root cause:** execution stopped before all CLI probes finished — see **Progress** above."
        )
        lines.append("")
        lines.append("**Fix plan:**")
        lines.append("1. Resolve the blocker (workspace registration, host executor, or runner toggle).")
        lines.append("2. Run **retry external execution** for another read-only pass.")
        lines.append("")
        lines.append("_No deploy or push was attempted._")
        return "\n".join(lines).strip()

    def _tick(ok: bool) -> str:
        return "✔" if ok else "✖"

    lines.append(
        f"- {_tick(analysis['whoami_ok'])} Railway whoami: "
        f"{'OK' if analysis['whoami_ok'] else 'failed or unavailable'}"
    )
    lines.append(
        f"- {_tick(analysis['status_ok'])} Railway status: "
        f"{'OK' if analysis['status_ok'] else 'failed or empty'}"
    )
    lines.append(
        f"- {_tick(analysis['logs_ok'])} Railway logs (tail): "
        f"{'OK' if analysis['logs_ok'] else 'failed or empty'}"
    )
    lines.append(
        f"- {_tick(analysis['git_ok'])} Git status: {'OK' if analysis['git_ok'] else 'failed'}"
    )
    lines.append("")
    issues: list[str] = []
    if not analysis["cli_present"] and not analysis["token_env_present"]:
        issues.append("No Railway CLI on PATH and no `RAILWAY_TOKEN` / `RAILWAY_API_TOKEN` in env.")
    elif not analysis["cli_present"]:
        issues.append("Railway CLI not found on PATH — API token env may still apply for some flows.")
    if not analysis["logs_ok"] and analysis["cli_present"]:
        issues.append("`railway logs` did not complete OK — see stderr under Verified checks.")
    if issues:
        lines.append("**Signals:**")
        for it in issues:
            lines.append(f"- {it}")
        lines.append("")
    lines.append("**Next steps:**")
    lines.append("1. Use the evidence above to adjust config or service settings.")
    lines.append("2. Say **retry external execution** after fixes for a fresh diagnostic pass.")
    lines.append("")
    if _operator_zero_nag():
        lines.append("_Deploy / push stays policy-gated until you explicitly approve._")
    else:
        lines.append("_Deploy / push remains blocked until you explicitly approve._")
    return "\n".join(lines).strip()


def format_investigation_for_chat(result: BoundedRailwayInvestigation) -> str:
    """User-facing block with verified snippets only."""
    preamble = _format_progress_preamble(result)

    lines: list[str] = [
        "### Verified checks (this host)",
        "",
    ]

    if result.skipped_reason:
        if _operator_zero_nag():
            reasons = {
                "runner_disabled": "Bounded runner is disabled on this host.",
                "host_executor_disabled": "Read-only probes did not start — local execution bridge is off on this API host.",
                "no_workspace": "No dev workspace path on file for this user on this host.",
                "no_user": "Missing user id for workspace lookup.",
                "workspace_path_missing": "Registered workspace path is not a directory on this host.",
            }
        else:
            reasons = {
                "runner_disabled": "External execution runner is disabled.",
                "host_executor_disabled": (
                    "I tried to start read-only checks, but host execution is disabled (`NEXA_HOST_EXECUTOR_ENABLED`)."
                ),
                "no_workspace": "I don't have a registered/local repo workspace to inspect.",
                "no_user": "Missing user id for workspace lookup.",
                "workspace_path_missing": "Registered workspace path is not a directory on this host.",
            }
        lines.append(reasons.get(result.skipped_reason, f"Skipped ({result.skipped_reason})."))
        lines.append("")
        lines.append("_Diagnostics only on this turn._" if _operator_zero_nag() else result.policy_note)
        core = "\n".join(lines).strip()
        summary = format_execution_summary_contract(result)
        return f"{preamble}{core}\n\n---\n\n{summary}".strip()

    if not result.railway_cli_present:
        lines.append(
            "**Railway CLI is not installed or not available in this environment.**"
        )
        if not getattr(result, "railway_env_token_present", False):
            lines.append("")
            lines.append(
                "**No credentials available:** set `RAILWAY_TOKEN` or `RAILWAY_API_TOKEN` on this worker, "
                "or install the Railway CLI (`railway`) and authenticate."
            )
        lines.append("")

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
    verified = "\n".join(lines).strip()
    summary = format_execution_summary_contract(result)
    return f"{preamble}{verified}\n\n---\n\n{summary}".strip()


__all__ = [
    "BoundedRailwayInvestigation",
    "analyze_investigation_for_contract",
    "format_execution_summary_contract",
    "format_investigation_for_chat",
    "investigation_to_public_payload",
    "run_bounded_railway_repo_investigation",
]
