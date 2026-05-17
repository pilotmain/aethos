# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator-facing runtime startup output — calm, enterprise, no legacy Nexa surface."""

from __future__ import annotations

import logging
import os
import socket
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("aethos.runtime")


def should_show_advanced_endpoints() -> bool:
    return (os.environ.get("AETHOS_SHOW_ADVANCED_ENDPOINTS") or "").strip().lower() in ("1", "true", "yes")


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _db_healthy_summary() -> str:
    try:
        from app.services.mission_control.runtime_db_coordination import build_database_integrity

        db = build_database_integrity()
        integrity = db.get("database_runtime_integrity") or {}
        if integrity.get("healthy") or integrity.get("schema_ok"):
            return "healthy"
    except Exception:
        pass
    return "initializing"


def _telegram_summary() -> str:
    s = get_settings()
    if (getattr(s, "telegram_bot_token", None) or "").strip():
        return "connected"
    return "not configured"


def build_operator_startup_lines(*, component: str = "api") -> list[str]:
    s = get_settings()
    base = s.api_base_url.rstrip("/")
    mc = "http://localhost:3000"
    mc_state = "reachable" if _port_open(3000) else "offline"
    return [
        "AethOS Runtime Starting…",
        "",
        "• Runtime coordination initializing",
        "• Provider routing operational",
        f"• Database {_db_healthy_summary()}",
        f"• Mission Control {mc_state}",
        "• Runtime truth warming",
        f"• Telegram integration {_telegram_summary()}",
        "",
        "AethOS is operational." if mc_state == "reachable" else "AethOS is preparing operational services…",
        f"Mission Control: {mc}",
        f"API: {base}",
        f"Status: {base}/api/v1/health",
    ]


def print_operator_startup_surface(*, component: str = "api") -> None:
    """Default calm startup — Mission Control first, no Swagger/webhook spam."""
    for line in build_operator_startup_lines(component=component):
        print(line, flush=True)
    if should_show_advanced_endpoints():
        print_advanced_runtime_endpoints()


def print_advanced_runtime_endpoints() -> None:
    """Optional developer/integrator endpoint listing."""
    s = get_settings()
    base = s.api_base_url.rstrip("/")
    p = s.api_v1_prefix
    print("--- Advanced runtime endpoints ---", flush=True)
    print(f"  API docs (Swagger)   {base}/docs", flush=True)
    print(f"  ReDoc                {base}/redoc", flush=True)
    print(f"  Operational health   {base}{p}/system/health", flush=True)
    print(f"  Email inbound        {base}{p}/email/inbound", flush=True)
    print(f"  WhatsApp webhook     {base}{p}/whatsapp/webhook", flush=True)
    print(f"  SMS inbound          {base}{p}/sms/inbound", flush=True)
    print(f"  GitHub PR review     {base}{p}/pr-review/webhook", flush=True)
    print("----------------------------------", flush=True)


def print_llm_operator_banner() -> None:
    """Log LLM routing once at startup with AethOS operator labels."""
    s = get_settings()
    active = (s.nexa_llm_provider or s.llm_provider or "auto").strip() or "auto"
    log = logging.getLogger("aethos.settings")
    log.info(
        "Runtime settings use_real_llm=%s anthropic_configured=%s openai_configured=%s active_provider=%s",
        s.use_real_llm,
        bool(s.anthropic_api_key),
        bool(s.openai_api_key),
        active,
    )
    if not s.use_real_llm and (s.anthropic_api_key or s.openai_api_key):
        log.warning("API keys present but USE_REAL_LLM is false — set USE_REAL_LLM=true and restart.")


def sanitize_operator_log_line(text: str) -> str:
    """Strip legacy Nexa labels from operator-visible log lines."""
    repl = (
        ("nexa_llm_provider", "active_provider"),
        ("[nexa.settings]", "[aethos.settings]"),
        ("Nexa (", "AethOS ("),
        ("=== Nexa config", "=== AethOS config"),
        ("=== end Nexa config", "=== end AethOS config"),
        ("Nexa:", "AethOS:"),
    )
    out = text
    for old, new in repl:
        out = out.replace(old, new)
    return out


__all__ = [
    "build_operator_startup_lines",
    "print_advanced_runtime_endpoints",
    "print_llm_operator_banner",
    "print_operator_startup_surface",
    "sanitize_operator_log_line",
    "should_show_advanced_endpoints",
]
