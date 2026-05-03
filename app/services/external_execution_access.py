"""
Access signals for end-to-end external execution asks (Railway + git + workspace).

Conservative: prefer asking for credentials over implying completed cloud work.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.dev_runtime.workspace import list_workspaces


@dataclass(frozen=True)
class ExternalExecutionAccess:
    """What Nexa can realistically use for an execution-shaped request."""

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
    return ExternalExecutionAccess(
        dev_workspace_registered=ws_ok,
        host_executor_enabled=host,
        railway_token_present=rtok,
        railway_cli_on_path=rcli,
        github_token_configured=bool(gh),
    )


def user_message_mentions_railway(user_text: str) -> bool:
    return "railway" in (user_text or "").lower()


def should_gate_external_execution(user_text: str, access: ExternalExecutionAccess) -> bool:
    """
    True → show access / connection reply instead of implying execution.

    Rules:
    - Mentioned Railway → need token or CLI proof on host for honest automation.
    - Always need a dev workspace for repo-shaped work.
    - Host executor off → cannot run local fix/push path from chat bridge.
    """
    if not access.dev_workspace_registered:
        return True
    if not access.host_executor_enabled:
        return True
    if user_message_mentions_railway(user_text):
        if not access.railway_token_present and not access.railway_cli_on_path:
            return True
    return False


def format_external_execution_access_reply(
    access: ExternalExecutionAccess,
    *,
    user_text: str = "",
) -> str:
    """Canonical ‘connect access’ copy — matches product expectation (truth-first)."""
    lines = [
        "Yes — Nexa can coordinate that kind of job **once access is in place**.",
        "",
        "**Right now I don’t have enough to execute it end-to-end:**",
    ]
    miss: list[str] = []
    if not access.dev_workspace_registered:
        miss.append("- **Dev workspace** — register a repo path under Mission Control → Dev / workspace.")
    if not access.host_executor_enabled:
        miss.append(
            "- **Host executor** — enable `NEXA_HOST_EXECUTOR_ENABLED` on the machine that runs Nexa "
            "so repo-local commands can run safely."
        )
    if user_message_mentions_railway(user_text):
        if not access.railway_token_present and not access.railway_cli_on_path:
            miss.append(
                "- **Railway** — provide `RAILWAY_TOKEN` (or API token) for the worker **or** install "
                "`railway` CLI and run `railway login` on the executor host."
            )
        elif access.railway_cli_on_path and not access.railway_token_present:
            miss.append(
                "- **Railway auth** — CLI is present; ensure `railway login` / token is valid on the worker."
            )
    if not access.github_token_configured:
        miss.append(
            "- **Git push (optional)** — configure `GITHUB_TOKEN` / repo remotes if pushes should run from Nexa."
        )
    if not miss:
        miss.append("- (No blocking items detected — if something still fails, paste the provider error.)")
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
