# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway NL: list Vercel / Railway projects when the user asks for deployment visibility."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.deployment.vercel_client import RailwayClient, VercelClient
from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import parse_deployment_status_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations


def try_gateway_deployment_status_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Answer phrases like ``check vercel projects`` using API / CLI where configured."""
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None

    settings = get_settings()
    if not bool(getattr(settings, "nexa_generic_deploy_enabled", False)):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None

    parsed = parse_deployment_status_intent(raw)
    if not parsed:
        return None

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    provider = (parsed.get("provider") or "").strip().lower()
    low = raw.lower()

    if not provider:
        body = (
            "**Which cloud should I check?**\n\n"
            "• `check vercel projects`\n"
            "• `check railway projects`\n\n"
            "_Requires `VERCEL_API_TOKEN` for Vercel API listing, or the Railway CLI logged in._"
        )
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body, source="deployment_status", user_text=raw),
            "intent": "deployment_status_prompt",
        }

    if provider == "vercel":
        token = getattr(settings, "vercel_api_token", None)
        data = VercelClient.list_projects(token)
        if isinstance(data, dict) and data.get("error"):
            err = str(data.get("message") or data.get("error"))
            body = f"**Cannot list Vercel projects**\n\n{err}"
        else:
            projects = (data or {}).get("projects") or []
            lines = [f"**Vercel projects ({len(projects)})**", ""]
            for p in projects[:15]:
                name = str(p.get("name") or "?")
                pid = str(p.get("id") or "")
                updated = str(p.get("updated_at") or "")[:10]
                lines.append(f"• **{name}** — `{pid[:10]}…` · updated {updated or '?'}")
            lines.append("")
            lines.append("Say **`deploy to vercel`** from your project folder to publish.")
            body = "\n".join(lines)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body.strip(), source="deployment_status_vercel", user_text=raw),
            "intent": "deployment_status",
        }

    if provider == "railway":
        data = RailwayClient.list_projects_json()
        if isinstance(data, dict) and data.get("error"):
            body = (
                "**Railway**\n\n"
                f"{data.get('message') or data.get('error')}\n\n"
                "Install the CLI (`brew install railway`) and run `railway login`, or open the Railway dashboard."
            )
        else:
            projects = (data or {}).get("projects") or []
            lines = [f"**Railway projects ({len(projects)})**", ""]
            for p in projects[:15]:
                nm = str(p.get("name") or "?")
                lines.append(f"• **{nm}**")
            lines.append("")
            lines.append("Say **`deploy to railway`** from a linked project directory when ready.")
            body = "\n".join(lines)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body.strip(), source="deployment_status_railway", user_text=raw),
            "intent": "deployment_status",
        }

    body = (
        f"I only support **vercel** or **railway** here (got `{provider}`).\n\n"
        "Try `check vercel projects` or `check railway projects`."
    )
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(body, source="deployment_status_unknown", user_text=raw),
        "intent": "deployment_status",
    }


__all__ = ["try_gateway_deployment_status_turn"]
