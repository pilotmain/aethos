# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""WhatsApp Cloud API webhooks — Channel Gateway (Phase 9)."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from starlette.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.gateway_events import audit_outbound_failure
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.rate_limit import GatewayRateLimitExceeded
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.sms_verify import verify_twilio_signature
from app.services.channel_gateway.whatsapp_adapter import extract_whatsapp_inbound_messages, get_whatsapp_adapter
from app.services.channel_gateway.whatsapp_send import send_whatsapp_text
from app.services.channel_gateway.whatsapp_twilio import is_twilio_whatsapp_from, twilio_form_to_whatsapp_raw_event
from app.services.channel_gateway.whatsapp_twilio_send import send_whatsapp_twilio_text
from app.services.channel_gateway.whatsapp_verify import verify_meta_webhook_signature
from app.services.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
orchestrator = OrchestratorService()


def _wa_configured_for_send() -> bool:
    s = get_settings()
    return bool(
        (s.whatsapp_access_token or "").strip() and (s.whatsapp_phone_number_id or "").strip()
    )


def _verify_post_signature(request: Request, raw: bytes) -> None:
    s = get_settings()
    secret = (s.whatsapp_app_secret or "").strip()
    if not secret:
        return
    sig = request.headers.get("x-hub-signature-256") or request.headers.get("X-Hub-Signature-256")
    if not verify_meta_webhook_signature(app_secret=secret, raw_body=raw, x_hub_signature_256=sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid webhook signature")


@router.get("/webhook")
async def whatsapp_verify_challenge(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta subscription verification (copy ``hub.challenge`` into 200 response)."""
    s = get_settings()
    expected = (s.whatsapp_verify_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp verify token not configured (WHATSAPP_VERIFY_TOKEN)",
        )
    if (hub_mode or "").strip() != "subscribe":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid hub.mode")
    if not hub_verify_token or not _verify_token_compare(expected, hub_verify_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid verify token")
    if hub_challenge is None or str(hub_challenge).strip() == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing hub.challenge")
    return PlainTextResponse(content=str(hub_challenge).strip())


def _verify_token_compare(expected: str, got: str) -> bool:
    return hmac.compare_digest((expected or "").strip(), (got or "").strip())


async def _verify_twilio_signature_if_configured(request: Request, form_params: dict[str, str]) -> None:
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


@router.post("/twilio-inbound")
async def whatsapp_twilio_inbound(request: Request) -> dict[str, Any]:
    """
    Twilio WhatsApp inbound (``application/x-www-form-urlencoded``, ``From=whatsapp:+…``).

    Opt-in via :envvar:`NEXA_WHATSAPP_TWILIO_INBOUND_ENABLED`. Reuses Meta :class:`WhatsAppAdapter`
    identity + normalization; outbound uses Twilio REST (not Meta Cloud).
    """
    s = get_settings()
    if not getattr(s, "nexa_whatsapp_twilio_inbound_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio WhatsApp inbound disabled (set NEXA_WHATSAPP_TWILIO_INBOUND_ENABLED=true)",
        )
    if not (s.twilio_account_sid or "").strip() or not (s.twilio_auth_token or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)",
        )

    form = await request.form()
    form_params = {str(k): str(v) for k, v in form.items()}
    await _verify_twilio_signature_if_configured(request, form_params)

    from_raw = str(form_params.get("From") or "").strip()
    if not is_twilio_whatsapp_from(from_raw):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expected WhatsApp From (whatsapp:+E164); use /sms/inbound for SMS",
        )
    try:
        raw_ev = twilio_form_to_whatsapp_raw_event(form_params)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not str(raw_ev.get("text") or "").strip():
        return {"ok": True, "processed": 0}

    db = SessionLocal()
    try:
        adapter = get_whatsapp_adapter()
        app_uid = adapter.resolve_app_user_id(db, raw_ev)
        orchestrator.users.get_or_create(db, app_uid)
        norm = adapter.normalize_message(raw_ev, app_user_id=app_uid)
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
                ) + "Permission required (missing permission id in envelope)."

        try:
            send_whatsapp_twilio_text(
                to_wa_digits=str(raw_ev.get("from") or ""),
                body=reply_body or "(no reply)",
                rate_limit_user_id=app_uid,
            )
        except GatewayRateLimitExceeded as rle:
            logger.warning("twilio whatsapp outbound rate limited: %s", rle)
            return {"ok": True, "response_kind": env.get("response_kind") or "chat", "outbound": False, "rate_limited": True}
        except Exception as exc:  # noqa: BLE001
            logger.exception("twilio whatsapp outbound failed: %s", exc)
            try:
                audit_outbound_failure(
                    db,
                    channel="whatsapp",
                    user_id=app_uid,
                    message=str(exc),
                    metadata={"stage": "outbound", "provider": "twilio"},
                )
            except Exception:  # noqa: BLE001
                pass
            return {"ok": True, "response_kind": env.get("response_kind") or "chat", "outbound": False}

        return {"ok": True, "response_kind": env.get("response_kind") or "chat", "outbound": True}
    finally:
        db.close()


@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_post_signature(request, raw)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid json") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid payload")

    messages = extract_whatsapp_inbound_messages(payload)
    if not messages:
        return {"ok": True}

    processed = 0
    for raw_ev in messages:
        if not str(raw_ev.get("text") or "").strip():
            continue
        db = SessionLocal()
        try:
            adapter = get_whatsapp_adapter()
            app_uid = adapter.resolve_app_user_id(db, raw_ev)
            orchestrator.users.get_or_create(db, app_uid)
            norm = adapter.normalize_message(raw_ev, app_user_id=app_uid)
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
                    ) + "Permission required (missing permission id in envelope)."

            if not _wa_configured_for_send():
                logger.warning("whatsapp inbound processed but outbound not configured")
                processed += 1
                continue

            try:
                send_whatsapp_text(
                    to_wa_id=str(raw_ev.get("from") or ""),
                    body=reply_body or "(no reply)",
                    rate_limit_user_id=app_uid,
                )
            except GatewayRateLimitExceeded as rle:
                logger.warning("whatsapp outbound rate limited: %s", rle)
            except Exception as exc:  # noqa: BLE001
                logger.exception("whatsapp outbound failed for user=%s: %s", raw_ev.get("from"), exc)
                try:
                    audit_outbound_failure(
                        db,
                        channel="whatsapp",
                        user_id=app_uid,
                        message=str(exc),
                        metadata={"stage": "outbound"},
                    )
                except Exception:  # noqa: BLE001
                    pass
            processed += 1
        finally:
            db.close()

    return {"ok": True, "processed": processed}
