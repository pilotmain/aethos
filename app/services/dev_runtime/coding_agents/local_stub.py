"""Non-destructive stub proving orchestration wiring."""

from __future__ import annotations

from typing import Any

from app.models.dev_runtime import NexaDevWorkspace
from app.services.dev_runtime.coding_agents.base import CodingAgentAdapter


class LocalStubCodingAgent(CodingAgentAdapter):
    def run(self, workspace: NexaDevWorkspace, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        return {
            "ok": True,
            "adapter": "local_stub",
            "workspace_id": workspace.id,
            "artifact": {
                "mode": "plan_only",
                "goal_preview": (goal or "")[:500],
                "note": "Stub adapter does not modify files; replace with Aider/Cursor/etc. later.",
            },
        }


__all__ = ["LocalStubCodingAgent"]
