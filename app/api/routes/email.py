"""Inbound email webhook — Channel Gateway (Phase 7)."""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.email_smtp import send_smtp_email
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.email_adapter import get_email_adapter
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.gateway_events import audit_outbound_failure
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.rate_limit import GatewayRateLimitExceeded
from app.services.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])
orchestrator = OrchestratorService()


class EmailInboundPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    from_address: str = Field(alias="from", description="Sender email")
    to: str | None = None
    subject: str = ""
    text: str = ""
    message_id: str | None = None
    thread_id: str | None = None
    attachments: list[Any] = Field(default_factory=list)

    @field_validator("from_address", mode="before")
    @classmethod
    def _coerce_from(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("from is required")
        return str(v).strip()


def _check_inbound_secret(request: Request) -> None:
    s = get_settings()
    secret = (s.email_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email inbound is not configured (EMAIL_WEBHOOK_SECRET)",
        )
    got = (request.headers.get("x-email-webhook-secret") or "").strip()
    if not got or not hmac.compare_digest(secret, got):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post("/inbound")
async def email_inbound(request: Request, payload: EmailInboundPayload) -> dict[str, Any]:
    """
    Receive a normalized inbound message (e.g. from your mail forwarder / automation).
    Authenticate with header ``X-Email-Webhook-Secret`` matching :envvar:`EMAIL_WEBHOOK_SECRET`.
    """
    _check_inbound_secret(request)

    raw: dict[str, Any] = {
        "from": payload.from_address,
        "subject": payload.subject,
        "text": payload.text,
        "message_id": payload.message_id,
        "thread_id": payload.thread_id,
        "attachments": payload.attachments,
    }
    if payload.to:
        raw["to"] = payload.to

    db = SessionLocal()
    try:
        adapter = get_email_adapter()
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
                ) + "Permission required (missing permission id in envelope)."

        subj_in = (payload.subject or "").strip()
        re_subj = f"Re: {subj_in}" if subj_in else "Re: Nexa"

        try:
            send_smtp_email(
                to_addr=payload.from_address.strip(),
                subject=re_subj,
                body=reply_body or "(no reply text)",
                rate_limit_user_id=app_uid,
            )
        except GatewayRateLimitExceeded:
            logger.warning("email outbound rate limited user=%s", app_uid)
            return {
                "ok": True,
                "response_kind": env.get("response_kind") or "chat",
                "rate_limited": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("email outbound failed: %s", exc)
            try:
                audit_outbound_failure(
                    db,
                    channel="email",
                    user_id=app_uid,
                    message=str(exc),
                    metadata={"stage": "outbound"},
                )
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not send email (check SMTP configuration)",
            ) from exc

        return {"ok": True, "response_kind": env.get("response_kind") or "chat"}
    finally:
        db.close()
