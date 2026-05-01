"""Non-destructive stub — default fallback when no other adapter is available."""

from __future__ import annotations

import json
from typing import Any

from app.services.dev_runtime.coding_agents.base import (
    CodingAgentAdapter,
    CodingAgentRequest,
    CodingAgentResult,
)


class LocalStubCodingAgent(CodingAgentAdapter):
    name = "local_stub"

    def available(self) -> bool:
        return True

    def run(self, request: CodingAgentRequest) -> CodingAgentResult:
        ctx = request.context or {}
        artifact = {
            "mode": "plan_only",
            "goal_preview": (request.goal or "")[:500],
            "note": "Stub adapter does not modify files; configure Aider/Cursor/etc. when ready.",
            "context_keys": list(ctx.keys())[:20],
        }
        summary = json.dumps(artifact, ensure_ascii=False, default=str)[:8000]
        return CodingAgentResult(
            ok=True,
            provider="local_stub",
            summary=summary,
            changed_files=[],
            commands_run=[],
            test_result=None,
            error=None,
        )


__all__ = ["LocalStubCodingAgent"]
