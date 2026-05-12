# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Access signals for end-to-end external execution asks (Railway + git + workspace).

Conservative: prefer asking for credentials over implying completed cloud work.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.dev_runtime.workspace import list_workspaces

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExternalExecutionAccess:
    """What AethOS can realistically use for an execution-shaped request."""

    dev_workspace_registered: bool
    host_executor_enabled: bool
    railway_token_present: bool
    railway_cli_on_path: bool
    github_token_configured: bool

    @property
    def railway_access_available(self) -> bool:
        """Env/API token or Railway CLI binary present on the worker host."""
        return self.railway_token_present or self.railway_cli_on_path


def assess_external_execution_access(db: Session | None, user_id: str | None) -> ExternalExecutionAccess:
    uid = (user_id or "").strip()
    ws_ok = False
    if db is not None and uid:
        try:
            ws_ok = len(list_workspaces(db, uid)) >= 1
        except Exception:
            ws_ok = False
    s = get_settings()
    host = bool(getattr(s, "nexa_host_executor_enabled", False))
    gh = bool((getattr(s, "github_token", None) or "").strip())
    rtok = bool(
        (os.environ.get("RAILWAY_TOKEN") or "").strip()
        or (os.environ.get("RAILWAY_API_TOKEN") or "").strip()
    )
    rcli = shutil.which("railway") is not None
    acc = ExternalExecutionAccess(
        dev_workspace_registered=ws_ok,
        host_executor_enabled=host,
        railway_token_present=rtok,
        railway_cli_on_path=rcli,
        github_token_configured=bool(gh),
    )
    _log.info(
        "ACCESS_DETECT user_id=%s workspace_registered=%s host_executor=%s "
        "railway_token_env=%s railway_cli_on_path=%s railway_access_available=%s",
        uid or None,
        acc.dev_workspace_registered,
        acc.host_executor_enabled,
        acc.railway_token_present,
        acc.railway_cli_on_path,
        acc.railway_access_available,
    )
    return acc


def user_message_mentions_railway(user_text: str) -> bool:
    return "railway" in (user_text or "").lower()


def _structural_external_execution_gate(user_text: str, access: ExternalExecutionAccess) -> bool:
    """Structural access check (Mission Control / legacy build_response) — ignores operator UX flags."""
    if not access.dev_workspace_registered:
        return True
    if not access.host_executor_enabled:
        return True
    if user_message_mentions_railway(user_text):
        if not access.railway_token_present and not access.railway_cli_on_path:
            return True
    return False


def should_gate_external_execution(
    user_text: str,
    access: ExternalExecutionAccess,
    *,
    for_mc_snapshot: bool = False,
) -> bool:
    """
    True → show access / connection reply instead of implying execution.

    Rules:
    - Mentioned Railway → need token or CLI proof on host for honest automation.
    - Always need a dev workspace for repo-shaped work.
    - Host executor off → cannot run local fix/push path from chat bridge.

    When ``nexa_operator_mode`` + ``nexa_operator_zero_nag`` are on and ``for_mc_snapshot`` is false,
    skip this gate so the bounded runner can return compact skip reasons instead of a long preamble.
    Mission Control snapshots pass ``for_mc_snapshot=True`` so ``requires_access`` stays structural.
    """
    if for_mc_snapshot:
        return _structural_external_execution_gate(user_text, access)
    try:
        s = get_settings()
        if bool(getattr(s, "nexa_operator_mode", False)) and bool(getattr(s, "nexa_operator_zero_nag", True)):
            return False
    except Exception:  # noqa: BLE001
        pass
    return _structural_external_execution_gate(user_text, access)


def _format_external_execution_access_reply_compact(
    access: ExternalExecutionAccess,
    *,
    user_text: str = "",
) -> str:
    """Short operator-mode summary — no multi-paragraph setup lecture."""
    miss: list[str] = []
    if not access.dev_workspace_registered:
        miss.append("- No dev workspace path on file for this user.")
    if not access.host_executor_enabled:
        miss.append("- Local run bridge is off on this API host.")
    if user_message_mentions_railway(user_text):
        if not access.railway_token_present and not access.railway_cli_on_path:
            miss.append(
                "- `RAILWAY_TOKEN` / `RAILWAY_API_TOKEN` is **not loaded in this worker** — add to `.env` on the API "
                "host (never in chat), then restart."
            )
        elif access.railway_cli_on_path and not access.railway_token_present:
            miss.append("- Railway CLI present; token not loaded in env.")
    if not access.github_token_configured:
        miss.append("- GitHub token not configured (optional for pushes).")
    if not miss:
        miss.append("- Bounded runner may still produce evidence on the next attempt.")
    body = (
        "AethOS on this worker reports **access** gaps for coordinated repo probes:\n" + "\n".join(miss)
    )
    return (
        f"{body}\n\nI can **coordinate** hosted checks after you fix the items above — say **retry external execution**, "
        "or use Vercel/GitHub-only operator turns for non-Railway work."
    )


def format_external_execution_access_reply(
    access: ExternalExecutionAccess,
    *,
    user_text: str = "",
) -> str:
    """Canonical ‘connect access’ copy — matches product expectation (truth-first)."""
    try:
        s = get_settings()
        if bool(getattr(s, "nexa_operator_mode", False)) and bool(getattr(s, "nexa_operator_zero_nag", True)):
            return _format_external_execution_access_reply_compact(access, user_text=user_text)
    except Exception:  # noqa: BLE001
        pass
    lines = [
        "Yes — AethOS can coordinate that kind of job **once access is in place**.",
        "",
        "**Right now I don’t have enough to execute it end-to-end:**",
    ]
    miss: list[str] = []
    if not access.dev_workspace_registered:
        miss.append("- **Dev workspace** — register a repo path under Mission Control → Dev / workspace.")
    if not access.host_executor_enabled:
        miss.append(
            "- **Host executor** — enable `NEXA_HOST_EXECUTOR_ENABLED` on the machine that runs AethOS "
            "so repo-local commands can run safely."
        )
    if user_message_mentions_railway(user_text):
        if not access.railway_token_present and not access.railway_cli_on_path:
            miss.append(
                "- **Railway** — `RAILWAY_TOKEN` / `RAILWAY_API_TOKEN` is **not loaded in this worker**. "
                "Add it to `.env` on the host that runs AethOS (not in chat), **`docker compose restart api bot`**, "
                "or install/authenticate the `railway` CLI on that host."
            )
        elif access.railway_cli_on_path and not access.railway_token_present:
            miss.append(
                "- **Railway auth** — CLI is present; ensure `railway login` / token is valid on the worker."
            )
    if not access.github_token_configured:
        miss.append(
            "- **Git push (optional)** — configure `GITHUB_TOKEN` / repo remotes if pushes should run from AethOS."
        )
    if not miss:
        miss.append(
            "- **Next:** say **retry external execution** after connecting access — you’ll see **progress** "
            "and **real CLI output** here (nothing counts as done without that evidence)."
        )
    lines.extend(miss)
    lines.extend(
        [
            "",
            "**Once connected, I can:** inspect logs where the CLI allows, work in your registered repo, "
            "run tests, propose commits, and **only then** describe deploy/health outcomes tied to real runs.",
            "",
            "_Nothing below this line counts as completed execution until those steps actually finish._",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "ExternalExecutionAccess",
    "assess_external_execution_access",
    "format_external_execution_access_reply",
    "should_gate_external_execution",
    "user_message_mentions_railway",
]
