# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Load agent_tools.json and expose enabled tools + prompt helpers."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.services.agent_runtime.defaults import DEFAULT_AGENT_TOOLS_MANIFEST
from app.services.agent_runtime.paths import agent_tools_manifest_path
from app.services.agent_runtime.workspace_files import atomic_write_json, read_json_file

logger = logging.getLogger(__name__)


def load_tool_manifest() -> dict[str, Any]:
    from app.services.agent_runtime.workspace_files import ensure_seed_files

    ensure_seed_files()
    path = agent_tools_manifest_path()
    data = read_json_file(path, DEFAULT_AGENT_TOOLS_MANIFEST)
    if not data.get("tools"):
        data = dict(DEFAULT_AGENT_TOOLS_MANIFEST)
        atomic_write_json(path, data)
    return data


def is_tool_enabled(tool_name: str) -> bool:
    if not get_settings().nexa_agent_tools_enabled:
        return False
    man = load_tool_manifest()
    for t in man.get("tools") or []:
        if (t.get("name") or "") == tool_name and t.get("enabled", True):
            return True
    return False


def get_tool_record(tool_name: str) -> dict[str, Any] | None:
    man = load_tool_manifest()
    for t in man.get("tools") or []:
        if (t.get("name") or "") == tool_name:
            return dict(t)
    return None


def list_tools_for_agent(_agent_handle: str) -> list[dict[str, Any]]:
    """Return manifest entries for tools are enabled globally (per-handle policy later)."""
    if not get_settings().nexa_agent_tools_enabled:
        return []
    man = load_tool_manifest()
    return [dict(t) for t in (man.get("tools") or []) if t.get("enabled", True)]


def format_tools_prompt_block() -> str:
    """Inject into agent system prompts so models only describe tools that exist."""
    tools = list_tools_for_agent("boss")
    if not tools:
        return (
            "Available governed tools: **none** (agent runtime tools are disabled or not configured).\n"
            "Do not claim you can spawn sessions or record heartbeats unless this list is non-empty."
        )
    lines = []
    for t in tools:
        nm = t.get("name") or "?"
        desc = (t.get("description") or "").strip()
        lines.append(f"- **{nm}**: {desc}")
    body = "\n".join(lines)
    return (
        "Available governed tools:\n"
        f"{body}\n\n"
        "Rules:\n"
        "- Describe a tool only if it appears above.\n"
        "- To use a tool, request a governed tool call via the Nexa API / agent runtime.\n"
        "- Do not claim tool execution unless the backend returns a successful result.\n"
    )
