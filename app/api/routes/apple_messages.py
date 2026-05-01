"""Apple Messages for Business (provider) inbound webhook — Channel Gateway (Phase 11)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, status

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.channel_gateway.apple_messages_adapter import (
    get_apple_messages_adapter,
    json_payload_to_raw_event,
)
from app.services.channel_gateway.apple_messages_send import send_apple_message_text
from app.services.channel_gateway.apple_messages_verify import verify_apple_messages_webhook_secret
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.gateway_events import audit_outbound_failure
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.rate_limit import GatewayRateLimitExceeded
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apple-messages", tags=["apple-messages"])
orchestrator = OrchestratorService()


def _outbound_configured() -> bool:
    s = get_settings()
    return bool(
        (s.apple_messages_provider_url or "").strip()
        and (s.apple_messages_access_token or "").strip()
        and (s.apple_messages_business_id or "").strip()
    )


def _check_webhook_secret(request: Request) -> None:
    s = get_settings()
    secret = (s.apple_messages_webhook_secret or "").strip()
    if not secret:
        return
    hdr = request.headers.get("X-Apple-Messages-Webhook-Secret") or request.headers.get(
        "x-apple-messages-webhook-secret"
    )
    if not verify_apple_messages_webhook_secret(configured_secret=secret, header_value=hdr):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid Apple Messages webhook secret",
        )


@router.post("/inbound")
async def apple_messages_inbound(
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """
    Generic provider webhook (JSON).

    Validates ``X-Apple-Messages-Webhook-Secret`` when :envvar:`APPLE_MESSAGES_WEBHOOK_SECRET` is set.
    """
    _check_webhook_secret(request)

    raw = json_payload_to_raw_event(body)
    if not str(raw.get("customer_id") or "").strip():
        raise HTTPException(status_code=400, detail="missing customer_id")

    db = SessionLocal()
    try:
        adapter = get_apple_messages_adapter()
        app_uid = adapter.resolve_app_user_id(db, raw)
        orchestrator.users.get_or_create(db, app_uid)
        norm = adapter.normalize_message(raw, app_user_id=app_uid)
        with bind_channel_origin(build_channel_origin(norm)):
            env = handle_incoming_channel_message(db, normalized_message=norm)

        reply_body = (env.get("message") or "").strip()
        pr = env.get("permission_required")
        if pr:
            try:
                pid = int(str(pr.get("permission_request_id") or pr.get("permission_id") or "0"))
            except (TypeError, ValueError):
                pid = 0
            if pid:
                reply_body = (
                    (reply_body + "\n\n") if reply_body else ""
                ) + format_email_permission_text(pid, app_uid)
            else:
                reply_body = (
                    (reply_body + "\n\n") if reply_body else ""
                ) + "Permission required (missing permission id)."

        if not _outbound_configured():
            logger.warning("apple messages inbound processed but provider outbound not configured")
            return {"ok": True, "response_kind": env.get("response_kind") or "chat", "outbound": False}

        cust = str(raw.get("customer_id") or "")
        outbound_sent = False
        try:
            send_apple_message_text(
                to=cust,
                body=reply_body or "(no reply)",
                rate_limit_user_id=app_uid,
            )
            outbound_sent = True
        except GatewayRateLimitExceeded as rle:
            logger.warning("apple messages outbound rate limited: %s", rle)
            return {
                "ok": True,
                "response_kind": env.get("response_kind") or "chat",
                "outbound": False,
                "rate_limited": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("apple messages outbound failed: %s", exc)
            try:
                audit_outbound_failure(
                    db,
                    channel="apple_messages",
                    user_id=app_uid,
                    message=str(exc),
                    metadata={"stage": "outbound"},
                )
            except Exception:  # noqa: BLE001
                pass

        return {
            "ok": True,
            "response_kind": env.get("response_kind") or "chat",
            "outbound": outbound_sent,
        }
    finally:
        db.close()
