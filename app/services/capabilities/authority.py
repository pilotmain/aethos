"""Capability snapshot for UX / prompts (host flags)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def get_capabilities() -> dict[str, Any]:
    s = get_settings()
    tools = bool(s.nexa_agent_tools_enabled)
    return {
        "spawn": tools,
        "heartbeat": tools,
        "write": True,
        "host": bool(s.nexa_host_executor_enabled),
        "web_search": bool(s.nexa_web_search_enabled),
        "web_fetch": bool(s.nexa_web_access_enabled),
        "web": bool(s.nexa_web_search_enabled or s.nexa_web_access_enabled),
    }
