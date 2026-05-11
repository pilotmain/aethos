"""Gateway NL: generic CLI deploy (opt-in; privileged owners only)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.services.deployment.executor import DeploymentExecutor
from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import parse_deploy_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations


def _deploy_workspace_root() -> str:
    s = get_settings()
    for attr in ("nexa_workspace_root", "nexa_command_work_root", "host_executor_work_root"):
        raw = str(getattr(s, attr, "") or "").strip()
        if raw:
            return raw
    return str(REPO_ROOT)


def try_gateway_deploy_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Run generic deploy when intent matches and settings + owner gate pass."""
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None

    settings = get_settings()
    if not bool(getattr(settings, "nexa_generic_deploy_enabled", False)):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None

    parsed = parse_deploy_intent(raw)
    if not parsed:
        return None

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    timeout = float(getattr(settings, "nexa_deploy_timeout_seconds", 300.0) or 300.0)
    workspace = _deploy_workspace_root()
    provider = parsed.get("provider")
    provider_str = str(provider).strip() if provider else None

    result = DeploymentExecutor.deploy_sync(
        workspace,
        provider=provider_str,
        timeout_seconds=timeout,
    )

    if result.get("success"):
        url = result.get("url") or "(see CLI output)"
        body = (
            f"✅ **DEPLOYMENT COMPLETE**\n\n"
            f"• Provider: **{result.get('provider')}**\n"
            f"• URL: {url}\n"
            f"• Command: `{result.get('command')}`\n"
        )
        if result.get("stdout"):
            body += f"\n```\n{str(result.get('stdout'))[:4000]}\n```\n"
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                body.strip(),
                source="generic_deploy",
                user_text=raw,
            ),
            "intent": "deployment_complete",
            "deployment": result,
        }

    avail = result.get("available_detected") or []
    hint = result.get("login_hint")
    err = result.get("error") or "Unknown error"
    lines = (
        f"❌ **DEPLOYMENT FAILED**\n\n"
        f"**Error:** {err}\n\n"
        f"💡 **Detected CLIs:** {avail if avail else 'none'}\n"
    )
    if hint:
        lines += f"\nTry: `{hint}`\n"
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(lines.strip(), source="generic_deploy_fail", user_text=raw),
        "intent": "deployment_failed",
        "deployment": result,
    }


__all__ = ["try_gateway_deploy_turn"]
