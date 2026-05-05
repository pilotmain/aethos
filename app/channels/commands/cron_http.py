"""HTTP client for Phase 13 cron API (Telegram/Slack/CLI share the same token)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings
logger = logging.getLogger(__name__)


def _base_urls() -> tuple[str, str]:
    s = get_settings()
    base = (s.api_base_url or "http://127.0.0.1:8000").rstrip("/")
    prefix = (s.api_v1_prefix or "/api/v1").rstrip("/")
    return base, prefix


def _auth_header() -> dict[str, str]:
    tok = (get_settings().nexa_cron_api_token or "").strip()
    if not tok:
        raise RuntimeError("missing_token")
    return {"Authorization": f"Bearer {tok}"}


def _headers_json() -> dict[str, str]:
    h = _auth_header()
    h["Content-Type"] = "application/json"
    return h


async def schedule_via_api(
    command_text: str,
    chat_id: str,
    *,
    channel: str = "telegram",
    slack_channel_id: str | None = None,
) -> str:
    """Parse `/schedule "cron" "action"` and POST /cron/jobs."""
    if not (get_settings().nexa_cron_api_token or "").strip():
        return (
            "Cron API is not configured. Set NEXA_CRON_API_TOKEN in .env (same value as the API) "
            "and restart the API so /schedule can register jobs."
        )
    line = (command_text or "").strip()
    m = re.match(r'^/?schedule\s+"([^"]+)"\s+"([^"]+)"\s*$', line)
    if not m:
        return (
            "Invalid format. Use:\n"
            '/schedule "0 9 * * *" "morning report"\n\n'
            "Five-field cron: minute hour day month weekday"
        )
    cron_expr, action_description = m.group(1), m.group(2)
    base, prefix = _base_urls()
    url = f"{base}{prefix}/cron/jobs"
    if channel == "slack":
        payload = {
            "channel": "slack",
            "channel_id": (slack_channel_id or chat_id).strip(),
            "message": f"⏰ Scheduled:\n{action_description}",
        }
    else:
        payload = {
            "channel": "telegram",
            "chat_id": chat_id,
            "message": f"⏰ Scheduled:\n{action_description}",
        }
    body = {
        "name": f"Cron: {action_description[:120]}",
        "cron_expression": cron_expr,
        "action_type": "channel_message",
        "action_payload": payload,
        "created_by": chat_id,
        "created_by_channel": channel,
        "timezone": get_settings().nexa_cron_default_timezone or "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=_headers_json(), json=body)
        if r.status_code >= 400:
            return f"Cron API error HTTP {r.status_code}: {r.text[:500]}"
        data = r.json()
        job = data.get("job") or {}
        jid = job.get("id", "?")
        return (
            f"✅ Cron job created\n"
            f"ID: `{jid}`\n"
            f"Schedule: `{cron_expr}`\n"
            f"Use /cron_list or /cron_remove {jid}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cron schedule_via_api failed")
        return f"Could not reach cron API ({exc}). Is the Nexa API running at {base}?"


async def cron_list_via_api() -> str:
    if not (get_settings().nexa_cron_api_token or "").strip():
        return "Set NEXA_CRON_API_TOKEN to list jobs."
    base, prefix = _base_urls()
    url = f"{base}{prefix}/cron/jobs"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, headers=_auth_header())
        if r.status_code >= 400:
            return f"List failed HTTP {r.status_code}"
        jobs = (r.json().get("jobs") or []) if r.headers.get("content-type", "").startswith("application/json") else []
    except Exception as exc:  # noqa: BLE001
        return f"Cron API unreachable: {exc}"
    if not jobs:
        return "No cron jobs."
    lines = ["📋 Cron jobs\n"]
    for j in jobs:
        lid = j.get("id", "?")
        lines.append(
            f"• `{lid}` — {j.get('name', '')}\n"
            f"  expr: `{j.get('cron_expression', '')}` runs={j.get('run_count', 0)}\n"
        )
    lines.append("Remove: /cron_remove <id>")
    return "\n".join(lines)[:3900]


async def cron_remove_via_api(command_text: str) -> str:
    if not (get_settings().nexa_cron_api_token or "").strip():
        return "Set NEXA_CRON_API_TOKEN to remove jobs."
    parts = (command_text or "").split()
    if len(parts) < 2:
        return "Usage: /cron_remove <job_id>"
    job_id = parts[1].strip()
    base, prefix = _base_urls()
    url = f"{base}{prefix}/cron/jobs/{job_id}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.delete(url, headers=_auth_header())
        if r.status_code == 404:
            return f"Job `{job_id}` not found."
        if r.status_code >= 400:
            return f"Remove failed HTTP {r.status_code}"
        return f"Removed job `{job_id}`."
    except Exception as exc:  # noqa: BLE001
        return f"Cron API error: {exc}"


def cron_cli_http(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Synchronous httpx for CLI (nexa_cli)."""
    tok = (get_settings().nexa_cron_api_token or "").strip()
    if not tok:
        raise SystemExit("Set NEXA_CRON_API_TOKEN and ensure the API is running.")
    base, prefix = _base_urls()
    url = f"{base}{prefix}{path}"
    auth = {"Authorization": f"Bearer {tok}"}
    with httpx.Client(timeout=60.0) as client:
        if method == "GET":
            r = client.get(url, headers=auth)
        elif method == "DELETE":
            r = client.delete(url, headers=auth)
        elif method == "POST":
            h = dict(auth)
            h["Content-Type"] = "application/json"
            r = client.post(url, headers=h, json=json_body or {})
        else:
            raise ValueError(method)
    if r.status_code >= 400:
        raise SystemExit(f"HTTP {r.status_code}: {r.text[:800]}")
    return r.json() if r.text.strip().startswith("{") else {"ok": True, "text": r.text}


__all__ = ["cron_cli_http", "cron_list_via_api", "cron_remove_via_api", "schedule_via_api"]
