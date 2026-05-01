"""Registry for coding-agent adapters (Phase 24)."""

from __future__ import annotations

from app.services.dev_runtime.coding_agents.aider_adapter import AiderCodingAgent
from app.services.dev_runtime.coding_agents.claude_code_adapter import ClaudeCodeAgent
from app.services.dev_runtime.coding_agents.codex_adapter import CodexCodingAgent
from app.services.dev_runtime.coding_agents.cursor_adapter import CursorCodingAgent
from app.services.dev_runtime.coding_agents.local_stub import LocalStubCodingAgent


def available_adapters():
    adapters = [
        LocalStubCodingAgent(),
        AiderCodingAgent(),
        CursorCodingAgent(),
        ClaudeCodeAgent(),
        CodexCodingAgent(),
    ]
    return [a for a in adapters if a.available()]


def choose_adapter(preferred: str | None = None):
    adapters = available_adapters()

    if preferred:
        pref = str(preferred).strip().lower().replace("-", "_")
        if pref in ("claude", "claude_code_cli"):
            pref = "claude_code"
        for adapter in adapters:
            if adapter.name == pref:
                return adapter

    for name in ("cursor", "claude_code", "codex", "aider", "local_stub"):
        for adapter in adapters:
            if adapter.name == name:
                return adapter

    return LocalStubCodingAgent()


__all__ = ["available_adapters", "choose_adapter"]
