"""Phase 24 — Aider adapter."""

from __future__ import annotations

import shutil

from app.services.dev_runtime.coding_agents.aider_adapter import AiderCodingAgent
from app.services.dev_runtime.coding_agents.base import CodingAgentRequest


def test_aider_unavailable_when_binary_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "true")
    monkeypatch.setenv("NEXA_AIDER_COMMAND", "aider_binary_that_does_not_exist_xyz")
    from app.core.config import get_settings

    get_settings.cache_clear()
    a = AiderCodingAgent()
    assert a.available() is False


def test_aider_disabled_via_env(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    monkeypatch.delenv("NEXA_AIDER_COMMAND", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    a = AiderCodingAgent()
    assert a.available() is False


def test_aider_request_structure(monkeypatch, tmp_path) -> None:
    """Smoke: adapter returns CodingAgentResult-shaped output."""
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "true")
    which = shutil.which("aider")
    if not which:
        return
    from app.core.config import get_settings

    get_settings.cache_clear()
    a = AiderCodingAgent()
    if not a.available():
        return
    req = CodingAgentRequest(
        user_id="u1",
        run_id="r1",
        workspace_id="w1",
        repo_path=str(tmp_path),
        goal="noop",
        context={},
        allow_write=False,
    )
    r = a.run(req)
    assert r.provider == "aider"
    assert isinstance(r.summary, str)
