# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator-facing Telegram polling ownership copy (Phase 4 Step 19)."""

from __future__ import annotations

import os
from typing import Any

from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status
from app.services.mission_control.runtime_service_registry import build_runtime_service_registry


def build_telegram_ownership_status() -> dict[str, Any]:
    own = build_runtime_ownership_status().get("runtime_ownership") or {}
    svc = build_runtime_service_registry().get("runtime_services") or {}
    tg_pid = own.get("telegram_polling_pid")
    api_count = int(svc.get("api_instance_count") or 0)
    bot_count = int(svc.get("telegram_instance_count") or 0)
    embed = bool(svc.get("embedded_api_detected"))
    from app.core.config import get_settings

    settings = get_settings()
    embed_enabled = bool(getattr(settings, "nexa_telegram_embed_with_api", True))

    mode = "none"
    message = "Telegram polling is not active."
    conflict = False

    if tg_pid and own.get("this_process_owns") and embed_enabled:
        mode = "embedded_api"
        message = (
            "Telegram polling is already managed by the active AethOS API runtime. "
            "Standalone bot will not start to avoid duplicate polling."
        )
    elif tg_pid and bot_count > 0:
        mode = "standalone_bot"
        message = "Telegram polling is currently managed by the standalone AethOS bot runtime."
    elif bot_count > 0 and api_count > 0 and embed_enabled:
        mode = "conflict"
        conflict = True
        message = "Telegram ownership conflict detected. Run: aethos runtime services"
    elif embed_enabled and api_count > 0:
        mode = "embedded_expected"
        message = "Telegram is configured for embedded API mode (NEXA_TELEGRAM_EMBED_WITH_API)."
    elif not (settings.telegram_bot_token or "").strip():
        mode = "unconfigured"
        message = "Telegram token not configured — bot will not start."

    return {
        "telegram_ownership": {
            "mode": mode,
            "message": message,
            "conflict": conflict,
            "embedded_enabled": embed_enabled,
            "polling_pid": tg_pid,
            "standalone_bot_processes": bot_count,
            "recommended_action": "aethos runtime services" if conflict else None,
            "bounded": True,
        }
    }


def format_telegram_lock_failure() -> str:
    return (
        "Telegram polling is already managed by another AethOS runtime process.\n"
        "Run `aethos runtime services` to inspect ownership, or `aethos restart runtime` to reconcile.\n"
    )
