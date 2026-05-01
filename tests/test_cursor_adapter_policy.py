"""Phase 24 — Cursor adapter guardrails."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.dev_runtime.coding_agents.base import CodingAgentRequest
from app.services.dev_runtime.coding_agents.cursor_adapter import CursorCodingAgent


def test_cursor_refuses_without_budget(monkeypatch, tmp_path) -> None:
    mock_s = MagicMock()
    mock_s.nexa_cursor_agent_enabled = True
    mock_s.cursor_api_key = "cursor-test-key"
    mock_s.nexa_cursor_agent_require_cost_budget = True
    mock_s.nexa_cursor_agent_max_cost_usd = 2.0
    with patch("app.services.dev_runtime.coding_agents.cursor_adapter.get_settings", return_value=mock_s):
        a = CursorCodingAgent()
        assert a.available() is True
        req = CodingAgentRequest(
            user_id="u",
            run_id="r",
            workspace_id="w",
            repo_path=str(tmp_path),
            goal="x",
            context={},
            cost_budget_usd=0,
        )
        r = a.run(req)
        assert r.ok is False
        assert r.error and "budget" in r.error.lower()


def test_cursor_disabled_without_key(monkeypatch, tmp_path) -> None:
    mock_s = MagicMock()
    mock_s.nexa_cursor_agent_enabled = True
    mock_s.cursor_api_key = ""
    with patch("app.services.dev_runtime.coding_agents.cursor_adapter.get_settings", return_value=mock_s):
        a = CursorCodingAgent()
        assert a.available() is False
