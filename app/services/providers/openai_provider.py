# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenAI chat completions — invoke **only** via :func:`~app.services.providers.gateway.call_provider`."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def call_openai(payload: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.services.providers.sdk import build_openai_client

    s = get_settings()
    key = (s.openai_api_key or "").strip()
    if not key:
        return {
            "error": "missing_api_key",
            "message": "OPENAI_API_KEY is not set — configure credentials to use OpenAI.",
        }

    task = str(payload.get("task") or payload.get("redacted") or "")
    if not task.strip():
        return {"error": "empty_task"}

    try:
        timeout = float(s.nexa_provider_timeout_seconds or 15.0)
        client = build_openai_client(api_key=key, timeout=timeout)
        resp = client.chat.completions.create(
            model=s.openai_model,
            messages=[{"role": "user", "content": task}],
            max_tokens=2048,
        )
        msg = resp.choices[0].message
        text = (msg.content or "").strip()
        return {
            "text": text,
            "model": getattr(resp, "model", None) or s.openai_model,
            "provider": "openai",
        }
    except Exception as exc:
        logger.warning("openai call failed: %s", exc)
        return {"error": "openai_failed", "detail": str(exc)}
