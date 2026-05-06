"""Backend capability truth for prompts (avoid LLM “legal mode” contradicting real flags)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def is_developer_workspace_mode() -> bool:
    return (get_settings().nexa_workspace_mode or "").strip().lower() == "developer"


def approvals_are_enabled(settings: Settings | None = None) -> bool:
    """Raw env toggle (`NEXA_APPROVALS_ENABLED`)."""
    s = settings or get_settings()
    return bool(getattr(s, "nexa_approvals_enabled", True))


def autonomy_test_mode(settings: Settings | None = None) -> bool:
    """
    Local-only autonomy test posture: developer workspace **and** approvals disabled.
    Regulated workspaces never activate this (fail closed).
    """
    s = settings or get_settings()
    if not is_developer_workspace_mode():
        return False
    return not approvals_are_enabled(s)


def audit_permission_bypassed(
    db: "Session",
    *,
    user_id: str | None,
    tool: str,
    scope: str = "agent_runtime",
    risk: str = "dev_mode",
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit `access.permission.bypassed` when developer autonomy mode skips approval gating."""
    from app.services.audit_service import audit
    from app.services.trust_audit_constants import ACCESS_PERMISSION_BYPASSED

    s = get_settings()
    md: dict[str, Any] = {
        "reason": (s.nexa_approval_bypass_reason or "").strip() or "local development testing",
        "workspace_mode": (s.nexa_workspace_mode or "regulated").strip().lower(),
        "approvals_enabled": bool(s.nexa_approvals_enabled),
        "tool": (tool or "")[:128],
        "scope": (scope or "")[:128],
        "risk": (risk or "")[:64],
    }
    if extra:
        for k, v in list(extra.items())[:24]:
            md[str(k)[:64]] = v
    audit(
        db,
        event_type=ACCESS_PERMISSION_BYPASSED,
        actor="aethos",
        user_id=user_id,
        message=f"Approval bypass ({tool}) scope={scope}",
        metadata=md,
    )


def get_runtime_truth() -> dict[str, bool]:
    """
    Reflect actual process capabilities for system prompts.
    Values are conservative booleans — prompts must align with these, not invent refusals.
    """
    s = get_settings()
    spawn = hb = False
    if s.nexa_agent_tools_enabled:
        try:
            from app.services.agent_runtime.tool_registry import is_tool_enabled

            spawn = is_tool_enabled("sessions_spawn")
            hb = is_tool_enabled("background_heartbeat")
        except Exception:  # noqa: BLE001
            spawn = hb = bool(s.nexa_agent_tools_enabled)
    file_access = bool(
        s.nexa_agent_tools_enabled or s.nexa_host_executor_enabled or s.cursor_enabled
    )
    return {
        "sessions_spawn": spawn,
        "heartbeat": hb,
        "file_access": file_access,
    }


def format_runtime_truth_prompt_block() -> str:
    """Short Markdown block injected into @boss / orchestrator system prompts."""
    t = get_runtime_truth()
    lines = [
        "**Runtime capability truth (this deployment)** — align replies with these facts; "
        "do **not** claim you are globally read-only, that **`sessions_spawn` is unavailable**, "
        "or that tools are **permanently locked** when the relevant flag is **true**:",
        "",
        f"- **`sessions_spawn` available:** {'yes' if t['sessions_spawn'] else 'no'}",
        f"- **`background_heartbeat` available:** {'yes' if t['heartbeat'] else 'no'}",
        f"- **Governed file / workspace execution path available:** {'yes' if t['file_access'] else 'no'}",
        "",
        "When a capability is **yes**, describe orchestration honestly; use approval policy wording instead "
        "of blanket refusal. Reserve hard blocks for unbounded recurring autonomy, unsupervised loops, "
        "and unrestricted system access.",
    ]
    return "\n".join(lines)


def log_guardrail_block(reason: str, *, detail: str | None = None, extra: dict[str, Any] | None = None) -> None:
    """Structured log line for guardrail decisions (searchable: `guardrail_block`)."""
    payload = {"reason": reason, "detail": (detail or "")[:500]}
    if extra:
        payload.update({k: v for k, v in list(extra.items())[:12]})
    logger.info("guardrail_block %s", payload)
