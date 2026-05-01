"""Twilio SMS inbound webhook — Channel Gateway (Phase 10)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.sms_adapter import get_sms_adapter, twilio_form_to_raw_event
from app.services.channel_gateway.gateway_events import audit_outbound_failure
from app.services.channel_gateway.sms_send import send_sms_text
from app.services.channel_gateway.sms_verify import verify_twilio_signature
from app.services.channel_gateway.rate_limit import GatewayRateLimitExceeded
from app.services.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms", tags=["sms"])
orchestrator = OrchestratorService()


def _twilio_configured_for_send() -> bool:
    s = get_settings()
    return bool(
        (s.twilio_account_sid or "").strip()
        and (s.twilio_auth_token or "").strip()
        and (s.twilio_from_number or "").strip()
    )


async def _verify_twilio_if_configured(request: Request, form_params: dict[str, str]) -> None:
    s = get_settings()
    token = (s.twilio_auth_token or "").strip()
    if not token:
        return
    sig = request.headers.get("X-Twilio-Signature") or request.headers.get("x-twilio-signature")
    url = str(request.url)
    if not verify_twilio_signature(
        url=url,
        post_params=form_params,
        auth_token=token,
        x_twilio_signature=sig,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid Twilio signature")


@router.post("/inbound")
async def sms_inbound_twilio(request: Request) -> dict[str, Any]:
    """
    Twilio SMS webhook (``application/x-www-form-urlencoded``).

    Validates ``X-Twilio-Signature`` when :envvar:`TWILIO_AUTH_TOKEN` is set.
    """
    form = await request.form()
    form_params = {str(k): str(v) for k, v in form.items()}
    await _verify_twilio_if_configured(request, form_params)

    raw = twilio_form_to_raw_event(form_params)
    if not str(raw.get("From") or "").strip():
        raise HTTPException(status_code=400, detail="missing From")

    db = SessionLocal()
    try:
        adapter = get_sms_adapter()
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

        if not _twilio_configured_for_send():
            logger.warning("sms inbound processed but Twilio outbound not configured")
            return {"ok": True, "response_kind": env.get("response_kind") or "chat", "outbound": False}

        frm = str(raw.get("From") or "")
        outbound_sent = False
        try:
            send_sms_text(
                to_e164=frm,
                body=reply_body or "(no reply)",
                rate_limit_user_id=app_uid,
            )
            outbound_sent = True
        except GatewayRateLimitExceeded as rle:
            logger.warning("sms outbound rate limited: %s", rle)
            return {
                "ok": True,
                "response_kind": env.get("response_kind") or "chat",
                "outbound": False,
                "rate_limited": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("sms outbound failed: %s", exc)
            try:
                audit_outbound_failure(
                    db,
                    channel="sms",
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
