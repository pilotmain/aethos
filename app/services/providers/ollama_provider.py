# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Local Ollama HTTP provider — invoke only via :func:`~app.services.providers.gateway.call_provider`."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def call_ollama(
    payload: dict[str, Any],
    *,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    POST ``/api/chat`` (non-streaming). Cost is treated as 0 in the token economy.

    Output shape aligns with OpenAI-style dicts: ``text``, ``model``, ``provider``.
    """
    import httpx

    task = str(payload.get("task") or payload.get("redacted") or "").strip()
    if not task:
        return {"error": "empty_task"}

    root = base_url.rstrip("/")
    url = f"{root}/api/chat"
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": task}],
        "stream": False,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("ollama HTTP error: %s", exc)
        return {"error": "ollama_http", "detail": str(exc), "status_code": exc.response.status_code}
    except Exception as exc:
        logger.warning("ollama request failed: %s", exc)
        return {"error": "ollama_failed", "detail": str(exc)}

    msg = data.get("message") if isinstance(data, dict) else None
    content = ""
    if isinstance(msg, dict):
        content = str(msg.get("content") or "").strip()
    if not content and isinstance(data, dict):
        # /api/generate-style fallback if misconfigured
        content = str(data.get("response") or "").strip()

    return {
        "text": content or "(empty response)",
        "model": str(data.get("model") or model) if isinstance(data, dict) else model,
        "provider": "ollama",
    }


__all__ = ["call_ollama"]
