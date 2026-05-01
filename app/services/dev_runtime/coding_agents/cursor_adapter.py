"""Cursor agent adapter — policy-gated; no remote execution wired in Phase 24."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.dev_runtime.coding_agents.base import (
    CodingAgentAdapter,
    CodingAgentRequest,
    CodingAgentResult,
)


class CursorCodingAgent(CodingAgentAdapter):
    name = "cursor"

    def available(self) -> bool:
        s = get_settings()
        if not s.nexa_cursor_agent_enabled:
            return False
        key = (s.cursor_api_key or "").strip()
        return bool(key)

    def run(self, request: CodingAgentRequest) -> CodingAgentResult:
        s = get_settings()
        if not self.available():
            return CodingAgentResult(
                ok=False,
                provider="cursor",
                summary="",
                changed_files=[],
                commands_run=[],
                error="cursor_adapter_disabled_or_missing_api_key",
            )
        budget = float(request.cost_budget_usd or 0.0)
        if s.nexa_cursor_agent_require_cost_budget and budget <= 0:
            return CodingAgentResult(
                ok=False,
                provider="cursor",
                summary="",
                changed_files=[],
                commands_run=[],
                error="cursor_requires_positive_cost_budget_usd",
            )
        max_usd = float(s.nexa_cursor_agent_max_cost_usd or 0.0)
        if budget > max_usd:
            return CodingAgentResult(
                ok=False,
                provider="cursor",
                summary="",
                changed_files=[],
                commands_run=[],
                error="cursor_cost_budget_exceeds_configured_max",
            )
        return CodingAgentResult(
            ok=False,
            provider="cursor",
            summary="",
            changed_files=[],
            commands_run=[],
            error="cursor_cloud_execution_not_enabled_yet",
        )


__all__ = ["CursorCodingAgent"]
