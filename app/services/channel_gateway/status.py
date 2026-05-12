# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Read-only channel configuration / health for admin surfaces (Phase 8)."""

from __future__ import annotations

from typing import Any, Literal

from app.core.config import get_settings
from app.services.channel_gateway.gateway_events import get_health_details

Health = Literal["ok", "missing_config", "disabled", "unknown"]


def _strip(s: str | None) -> str:
    return (s or "").strip()


def _has(s: str | None) -> bool:
    return bool(_strip(s))


def _public_base_notes(api_base: str) -> list[str]:
    b = _strip(api_base)
    notes: list[str] = []
    if not b:
        notes.append("Set API_BASE_URL to display public webhook URLs and valid email permission links.")
        return notes
    low = b.lower()
    if "localhost" in low or "127.0.0.1" in low:
        notes.append(
            "API_BASE_URL points to localhost — use a publicly reachable URL for Slack/Email webhooks "
            "and email approval links in production."
        )
    return notes


def build_channel_status_list() -> list[dict[str, Any]]:
    """Returns sanitized channel rows (no secret values)."""
    s = get_settings()
    base = _strip(s.api_base_url).rstrip("/")
    p = _strip(s.api_v1_prefix) or "/api/v1"
    if not p.startswith("/"):
        p = "/" + p
    prefix = f"{base}{p}" if base else ""

    def full(path_suffix: str) -> str | None:
        if not base:
            return None
        tail = path_suffix if path_suffix.startswith("/") else f"/{path_suffix}"
        return f"{prefix}{tail}"

    base_notes = _public_base_notes(s.api_base_url or "")

    # --- Web (always on) ---
    web_chan: dict[str, Any] = {
        "channel": "web",
        "label": "Web",
        "available": True,
        "configured": True,
        "enabled": True,
        "health": "ok",
        "webhook_url": None,
        "webhook_urls": None,
        "missing": [],
        "notes": ["Built-in chat UI — no inbound webhook."],
    }

    # --- Telegram ---
    tg_missing: list[str] = []
    if not _has(s.telegram_bot_token):
        tg_missing.append("TELEGRAM_BOT_TOKEN")
    tg_configured = len(tg_missing) == 0
    tg_health: Health = "ok" if tg_configured else "missing_config"
    tg_notes = list(base_notes)
    telegram_chan: dict[str, Any] = {
        "channel": "telegram",
        "label": "Telegram",
        "available": True,
        "configured": tg_configured,
        "enabled": tg_configured,
        "health": tg_health,
        "webhook_url": None,
        "webhook_urls": None,
        "missing": tg_missing,
        "notes": tg_notes + ["Bot uses long polling — no HTTP webhook URL on the API."],
    }

    # --- Slack ---
    slack_missing: list[str] = []
    if not _has(s.slack_bot_token):
        slack_missing.append("SLACK_BOT_TOKEN")
    if not _has(s.slack_signing_secret):
        slack_missing.append("SLACK_SIGNING_SECRET")
    slack_configured = len(slack_missing) == 0
    slack_health: Health = "ok" if slack_configured else "missing_config"
    slack_urls = {
        "events": full("/slack/events"),
        "interactions": full("/slack/interactions"),
    }
    slack_notes = list(base_notes)
    slack_chan: dict[str, Any] = {
        "channel": "slack",
        "label": "Slack",
        "available": True,
        "configured": slack_configured,
        "enabled": slack_configured,
        "health": slack_health,
        "webhook_url": slack_urls.get("events"),
        "webhook_urls": slack_urls,
        "missing": slack_missing,
        "notes": slack_notes,
    }

    # --- Email ---
    email_missing: list[str] = []
    if not _has(s.email_webhook_secret):
        email_missing.append("EMAIL_WEBHOOK_SECRET")
    if not _has(s.smtp_host):
        email_missing.append("SMTP_HOST")
    if not _has(s.email_from):
        email_missing.append("EMAIL_FROM")
    email_configured = len(email_missing) == 0
    email_health: Health = "ok" if email_configured else "missing_config"
    email_notes = list(base_notes)
    if email_configured:
        if not _has(s.smtp_user):
            email_notes.append("SMTP_USER is not set — required if your SMTP server needs authentication.")
        if not _has(s.smtp_password):
            email_notes.append("SMTP_PASSWORD is not set — required if your SMTP server needs authentication.")
    if not _has(s.api_base_url) or not base:
        email_notes.append("API_BASE_URL is required for correct email permission approval links.")
    email_urls = {"inbound": full("/email/inbound")}
    email_chan: dict[str, Any] = {
        "channel": "email",
        "label": "Email",
        "available": True,
        "configured": email_configured,
        "enabled": email_configured,
        "health": email_health,
        "webhook_url": email_urls.get("inbound"),
        "webhook_urls": email_urls,
        "missing": email_missing,
        "notes": email_notes,
    }

    # --- WhatsApp (Cloud API) ---
    wa_missing: list[str] = []
    if not _has(s.whatsapp_access_token):
        wa_missing.append("WHATSAPP_ACCESS_TOKEN")
    if not _has(s.whatsapp_phone_number_id):
        wa_missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if not _has(s.whatsapp_verify_token):
        wa_missing.append("WHATSAPP_VERIFY_TOKEN")
    wa_configured = len(wa_missing) == 0
    wa_health: Health = "ok" if wa_configured else "missing_config"
    wa_notes = list(base_notes)
    if wa_configured and not _has(s.whatsapp_app_secret):
        wa_notes.append(
            "WHATSAPP_APP_SECRET is not set — webhook POST signatures will not be verified (dev-only risk)."
        )
    wa_urls = {"webhook": full("/whatsapp/webhook")}
    wa_chan: dict[str, Any] = {
        "channel": "whatsapp",
        "label": "WhatsApp",
        "available": True,
        "configured": wa_configured,
        "enabled": wa_configured,
        "health": wa_health,
        "webhook_url": wa_urls.get("webhook"),
        "webhook_urls": wa_urls,
        "missing": wa_missing,
        "notes": wa_notes,
    }

    # --- SMS (Twilio) ---
    sms_missing: list[str] = []
    if not _has(s.twilio_account_sid):
        sms_missing.append("TWILIO_ACCOUNT_SID")
    if not _has(s.twilio_auth_token):
        sms_missing.append("TWILIO_AUTH_TOKEN")
    if not _has(s.twilio_from_number):
        sms_missing.append("TWILIO_FROM_NUMBER")
    sms_configured = len(sms_missing) == 0
    sms_health: Health = "ok" if sms_configured else "missing_config"
    sms_notes = list(base_notes)
    if not _has(s.twilio_auth_token):
        sms_notes.append(
            "TWILIO_AUTH_TOKEN is not set — inbound SMS webhooks will not be signature-verified "
            "(acceptable only in trusted local/dev)."
        )
    if not base:
        sms_notes.append("API_BASE_URL is required to show the public Twilio webhook URL in this list.")
    sms_urls = {"inbound": full("/sms/inbound")}
    sms_chan: dict[str, Any] = {
        "channel": "sms",
        "label": "SMS (Twilio)",
        "available": True,
        "configured": sms_configured,
        "enabled": sms_configured,
        "health": sms_health,
        "webhook_url": sms_urls.get("inbound"),
        "webhook_urls": sms_urls,
        "missing": sms_missing,
        "notes": sms_notes,
    }

    # --- Apple Messages for Business (provider) ---
    am_missing: list[str] = []
    if not _has(s.apple_messages_provider_url):
        am_missing.append("APPLE_MESSAGES_PROVIDER_URL")
    if not _has(s.apple_messages_access_token):
        am_missing.append("APPLE_MESSAGES_ACCESS_TOKEN")
    if not _has(s.apple_messages_business_id):
        am_missing.append("APPLE_MESSAGES_BUSINESS_ID")
    if not _has(s.apple_messages_webhook_secret):
        am_missing.append("APPLE_MESSAGES_WEBHOOK_SECRET")
    am_configured = len(am_missing) == 0
    am_health: Health = "ok" if am_configured else "missing_config"
    am_notes = list(base_notes)
    if not _has(s.apple_messages_webhook_secret):
        am_notes.append(
            "APPLE_MESSAGES_WEBHOOK_SECRET is not set — inbound webhooks will not be verified "
            "(acceptable only in trusted local/dev)."
        )
    if not base:
        am_notes.append("API_BASE_URL is required to show the public Apple Messages webhook URL in this list.")
    am_notes.append(
        "Apple Messages for Business typically requires Apple approval and a registered Business Chat provider."
    )
    am_urls = {"inbound": full("/apple-messages/inbound")}
    am_chan: dict[str, Any] = {
        "channel": "apple_messages",
        "label": "Apple Messages (Business)",
        "available": True,
        "configured": am_configured,
        "enabled": am_configured,
        "health": am_health,
        "webhook_url": am_urls.get("inbound"),
        "webhook_urls": am_urls,
        "missing": am_missing,
        "notes": am_notes,
    }

    rows = [web_chan, telegram_chan, slack_chan, email_chan, wa_chan, sms_chan, am_chan]
    for r in rows:
        hd = get_health_details(str(r.get("channel") or ""))
        if hd:
            r["health_details"] = hd
    return rows
