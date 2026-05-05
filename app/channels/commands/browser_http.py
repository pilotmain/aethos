"""HTTP client for Phase 14 browser API (Telegram / Slack — Bearer ``NEXA_CRON_API_TOKEN``)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _base_urls() -> tuple[str, str]:
    s = get_settings()
    base = (s.api_base_url or "http://127.0.0.1:8000").rstrip("/")
    prefix = (s.api_v1_prefix or "/api/v1").rstrip("/")
    return base, prefix


def _headers_json() -> dict[str, str]:
    tok = (get_settings().nexa_cron_api_token or "").strip()
    if not tok:
        raise RuntimeError("missing_token")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


async def browser_via_api(command_line: str) -> str:
    """
    Parse `/browser …` text and call the API.

    navigate <url> | screenshot | click <selector> | fill <selector> <value> | text <selector> | evaluate <js>
    """
    tok = (get_settings().nexa_cron_api_token or "").strip()
    if not tok:
        return (
            "Browser API needs NEXA_CRON_API_TOKEN (same Bearer as cron) in .env for the bot and API. "
            "Restart both after setting."
        )

    raw = (command_line or "").strip()
    low = raw.lower()
    if not low.startswith("/browser"):
        return "Internal: expected /browser command."
    rest = raw[len("/browser") :].strip()
    if not rest:
        return (
            "🌐 Browser commands (Phase 14):\n"
            "/browser navigate <url>\n"
            "/browser screenshot\n"
            "/browser click <css_selector>\n"
            "/browser fill <selector> <value>\n"
            "/browser text <selector>\n"
            "/browser html\n"
            "/browser evaluate <javascript>"
        )

    parts = rest.split()
    action = parts[0].lower()
    base, prefix = _base_urls()
    h = _headers_json()

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            if action == "navigate":
                url = rest[len("navigate") :].strip()
                if not url:
                    return "Usage: /browser navigate https://example.com"
                r = await client.post(
                    f"{base}{prefix}/browser/navigate",
                    headers=h,
                    json={"url": url, "wait_until": "domcontentloaded"},
                )
            elif action == "screenshot":
                r = await client.get(f"{base}{prefix}/browser/screenshot", headers=h)
            elif action == "click" and len(parts) >= 2:
                sel = parts[1]
                r = await client.post(f"{base}{prefix}/browser/click", headers=h, json={"selector": sel})
            elif action == "fill" and len(parts) >= 3:
                sel, val = parts[1], " ".join(parts[2:])
                r = await client.post(
                    f"{base}{prefix}/browser/fill",
                    headers=h,
                    json={"selector": sel, "value": val},
                )
            elif action == "text" and len(parts) >= 2:
                sel = parts[1]
                r = await client.post(f"{base}{prefix}/browser/text", headers=h, json={"selector": sel})
            elif action == "html":
                r = await client.post(f"{base}{prefix}/browser/html", headers=h, json={})
            elif action == "evaluate":
                script = rest[len("evaluate") :].strip()
                if not script:
                    return "Usage: /browser evaluate document.title"
                r = await client.post(
                    f"{base}{prefix}/browser/evaluate",
                    headers=h,
                    json={"script": script},
                )
            else:
                return (
                    "Unknown /browser subcommand. Try `/browser` alone for usage."
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("browser_http request failed")
            return f"Browser API error: {exc}"[:3500]

    try:
        data = r.json()
    except Exception:
        return (r.text or r.reason_phrase or "browser API error")[:3500]

    if r.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else str(data)
        return f"❌ {detail}"[:3500]

    if not isinstance(data, dict):
        return str(data)[:3500]

    if action == "screenshot" and data.get("screenshot_path"):
        return f"📸 Screenshot saved:\n{data.get('screenshot_path')}"
    return str(data.get("output") or data)[:3900]


__all__ = ["browser_via_api"]
