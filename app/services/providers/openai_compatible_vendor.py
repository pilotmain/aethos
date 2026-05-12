# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
OpenAI-compatible remote vendors (DeepSeek, OpenRouter) — call only from :mod:`app.services.providers.gateway`.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from app.core.config import get_settings
from app.services.llm_usage_context import resolve_db_for_usage
from app.services.llm_usage_recorder import _tok_from_openai_response, record_llm_usage
from app.services.providers.sdk import build_openai_client

logger = logging.getLogger(__name__)

Vendor = Literal["deepseek", "openrouter"]


def call_openai_compatible_vendor(payload: dict[str, Any], *, vendor: Vendor) -> dict[str, Any]:
    s = get_settings()
    if vendor == "deepseek":
        key = (s.deepseek_api_key or "").strip()
        base = (s.deepseek_base_url or "").strip() or "https://api.deepseek.com/v1"
        model = (s.deepseek_model or "deepseek-chat").strip()
        label = "deepseek"
    else:
        key = (s.openrouter_api_key or "").strip()
        base = (s.openrouter_base_url or "").strip() or "https://openrouter.ai/api/v1"
        model = (s.openrouter_model or "openai/gpt-4o-mini").strip()
        label = "openrouter"
    if not key:
        return {
            "error": "missing_api_key",
            "message": f"{label.upper()}_API_KEY is not set — configure credentials to use {label}.",
        }

    task = str(payload.get("task") or payload.get("redacted") or "")
    if not task.strip():
        return {"error": "empty_task"}

    try:
        timeout = float(s.nexa_provider_timeout_seconds or 15.0)
        client = build_openai_client(api_key=key, base_url=base, timeout=timeout)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": task}],
            max_tokens=2048,
        )
        try:
            it, ot, _t = _tok_from_openai_response(resp)
            record_llm_usage(
                resolve_db_for_usage(),
                provider=label,
                model=model,
                input_tokens=it,
                output_tokens=ot,
                used_user_key=False,
            )
        except Exception:  # noqa: BLE001
            pass
        msg = resp.choices[0].message
        text = (msg.content or "").strip()
        return {
            "text": text,
            "model": getattr(resp, "model", None) or model,
            "provider": label,
        }
    except Exception as exc:
        logger.warning("%s call failed: %s", label, exc)
        return {"error": f"{label}_failed", "detail": str(exc)}


__all__ = ["call_openai_compatible_vendor"]
