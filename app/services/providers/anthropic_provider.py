"""Anthropic Messages API — invoke **only** via :func:`~app.services.providers.gateway.call_provider`."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def call_anthropic(payload: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.services.providers.sdk import build_anthropic_client

    s = get_settings()
    key = (s.anthropic_api_key or "").strip()
    if not key:
        return {
            "error": "missing_api_key",
            "message": "ANTHROPIC_API_KEY is not set — configure credentials to use Anthropic.",
        }

    task = str(payload.get("task") or payload.get("redacted") or "")
    if not task.strip():
        return {"error": "empty_task"}

    try:
        timeout = float(s.nexa_provider_timeout_seconds or 15.0)
        client = build_anthropic_client(api_key=key, timeout=timeout)
        msg = client.messages.create(
            model=s.anthropic_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": task}],
        )
        parts: list[str] = []
        for block in msg.content:
            if getattr(block, "type", None) == "text" and hasattr(block, "text"):
                parts.append(block.text)
        text = "".join(parts).strip()
        return {
            "text": text,
            "model": getattr(msg, "model", None) or s.anthropic_model,
            "provider": "anthropic",
        }
    except Exception as exc:
        logger.warning("anthropic call failed: %s", exc)
        return {"error": "anthropic_failed", "detail": str(exc)}
