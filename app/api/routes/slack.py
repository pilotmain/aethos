"""Slack Events API + Interactions — Channel Gateway (Phase 6)."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.channel_user import ChannelUser
from app.services.access_permissions import deny_permission as ap_deny_permission
from app.services.access_permissions import grant_permission as ap_grant_permission
from app.services.channel_gateway.gateway_events import audit_outbound_failure
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.slack_adapter import get_slack_adapter
from app.services.channel_gateway.slack_api import slack_chat_post_message
from app.services.channel_gateway.slack_blocks import grant_mode_for_action, permission_blocks
from app.services.channel_gateway.slack_verify import slack_sig_headers, verify_slack_signature
from app.services.orchestrator_service import OrchestratorService
from app.services.permission_resume_execution import PermissionResumeError, resume_host_executor_after_grant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])
orchestrator = OrchestratorService()


def _require_slack_config():
    s = get_settings()
    if not (s.slack_bot_token or "").strip() or not (s.slack_signing_secret or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack is not configured (SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET)",
        )
    return s


async def _verify_slack_request(request: Request) -> bytes:
    s = _require_slack_config()
    raw = await request.body()
    ts, sig = slack_sig_headers(dict(request.headers))
    if not verify_slack_signature(
        signing_secret=s.slack_signing_secret.strip(),
        request_timestamp=ts,
        raw_body=raw,
        slack_signature=sig,
    ):
        raise HTTPException(status_code=401, detail="invalid slack signature")
    return raw


def _slack_user_to_owner(db: Session, slack_user_id: str) -> str | None:
    row = db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == "slack",
            ChannelUser.channel_user_id == slack_user_id.strip(),
        )
    )
    return row.user_id if row else None


def _post_response_url(url: str | None, text: str) -> None:
    if not url:
        return
    try:
        httpx.post(url, json={"text": text}, timeout=10.0)
    except Exception as exc:  # noqa: BLE001
        logger.info("slack response_url post failed: %s", exc)


@router.post("/events")
async def slack_events(request: Request) -> dict[str, Any]:
    raw = await _verify_slack_request(request)
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")

    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    if data.get("type") != "event_callback":
        return {"ok": True}

    team_id = str(data.get("team_id") or "").strip()
    ev = data.get("event") or {}
    et = ev.get("type")

    if et != "message":
        return {"ok": True}

    if ev.get("bot_id") or ev.get("subtype") in (
        "bot_message",
        "message_changed",
        "message_deleted",
    ):
        return {"ok": True}
    if not ev.get("user"):
        return {"ok": True}

    db = SessionLocal()
    try:
        wrapper: dict[str, Any] = {"event": ev, "team_id": team_id}
        adapter = get_slack_adapter()
        app_uid = adapter.resolve_app_user_id(db, wrapper)
        orchestrator.users.get_or_create(db, app_uid)
        norm = adapter.normalize_message(wrapper, app_user_id=app_uid)
        with bind_channel_origin(build_channel_origin(norm)):
            env = handle_incoming_channel_message(db, normalized_message=norm)

        token = (get_settings().slack_bot_token or "").strip()
        if not token:
            return {"ok": True}

        ch = str(ev.get("channel") or "")
        thread_ref = str(ev.get("thread_ts")).strip() if ev.get("thread_ts") else None
        text_out = (env.get("message") or "")[:39000]
        pr = env.get("permission_required")
        blocks = None
        if pr:
            blocks = permission_blocks(pr=pr, channel_for_reply=ch)
            text_out = text_out or "🔐 Permission required — use the buttons below."
        try:
            slack_chat_post_message(
                token,
                channel=ch,
                text=text_out,
                thread_ts=thread_ref,
                blocks=blocks,
                rate_limit_user_id=app_uid,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack outbound failed: %s", exc)
            try:
                audit_outbound_failure(
                    db,
                    channel="slack",
                    user_id=app_uid,
                    message=str(exc),
                    metadata={"stage": "outbound"},
                )
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("slack events handler failed: %s", exc)
    finally:
        db.close()

    return {"ok": True}


@router.post("/interactions")
async def slack_interactions(request: Request) -> dict[str, Any]:
    raw = await _verify_slack_request(request)
    try:
        form = parse_qs(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid form body")

    payload_raw = (form.get("payload") or [""])[0]
    if not payload_raw:
        raise HTTPException(status_code=400, detail="missing payload")

    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid payload json")

    if payload.get("type") != "block_actions":
        return {"ok": True}

    response_url = payload.get("response_url")
    user_slack = (payload.get("user") or {}).get("id")
    if not user_slack:
        _post_response_url(response_url, "Could not verify Slack user.")
        return {"ok": True}

    actions = payload.get("actions") or []
    if not actions:
        return {"ok": True}

    action = actions[0]
    try:
        value_obj = json.loads(action.get("value") or "{}")
    except json.JSONDecodeError:
        _post_response_url(response_url, "Invalid button payload.")
        return {"ok": True}

    permission_id = int(value_obj.get("permission_id") or 0)
    action_kind = str(value_obj.get("action") or "").strip()
    if not permission_id or not action_kind:
        _post_response_url(response_url, "Missing permission reference.")
        return {"ok": True}

    db = SessionLocal()
    try:
        owner = _slack_user_to_owner(db, str(user_slack))
        if not owner:
            _post_response_url(
                response_url,
                "Your Slack user is not linked in Nexa yet — send a message to the bot first.",
            )
            return {"ok": True}

        if action_kind == "deny":
            row = ap_deny_permission(db, owner, permission_id)
            if not row:
                _post_response_url(response_url, "Could not deny (not found or not pending).")
                return {"ok": True}
            _post_response_url(response_url, "Denied.")
            return {"ok": True}

        if action_kind not in ("approve_once", "approve_session"):
            _post_response_url(response_url, "Unknown action.")
            return {"ok": True}

        gm = grant_mode_for_action(
            "approve_session" if action_kind == "approve_session" else "approve_once"
        )
        granted = ap_grant_permission(
            db,
            owner,
            permission_id,
            granted_by_user_id=owner,
            grant_mode=gm,
        )
        if not granted:
            _post_response_url(response_url, "Could not grant (not pending?).")
            return {"ok": True}

        reply = "Permission granted."
        try:
            jid = resume_host_executor_after_grant(db, owner, permission_id, web_session_id=None)
            reply = f"Permission granted. Host job #{jid} queued."
        except PermissionResumeError as e:
            reply = f"Granted, but could not resume the action: {e}"

        _post_response_url(response_url, reply[:2000])
    finally:
        db.close()

    return {"ok": True}
