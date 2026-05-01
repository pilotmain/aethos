"""Reserved for Cursor Agent / SDK integration."""

from __future__ import annotations

from typing import Any

from app.models.dev_runtime import NexaDevWorkspace
from app.services.dev_runtime.coding_agents.base import CodingAgentAdapter


class CursorCodingAgentAdapter(CodingAgentAdapter):
    def run(self, workspace: NexaDevWorkspace, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        _ = workspace, goal, context
        return {"ok": False, "error": "cursor_adapter_not_implemented"}


__all__ = ["CursorCodingAgentAdapter"]
