"""Operator zero-nag — compact access copy, phrase scrubbing, gate bypass."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.external_execution_access import (
    ExternalExecutionAccess,
    format_external_execution_access_reply,
    should_gate_external_execution,
)
from app.services.gateway.runtime import gateway_finalize_operator_or_execution_reply
from app.services.intent_focus_filter import apply_operator_zero_nag_surface


def test_apply_operator_zero_nag_surface_strips_phrases() -> None:
    raw = (
        "Yes once access is in place we can proceed.\n\n"
        "Right now I don't have enough context.\n"
        "register a repo path under dev\n"
        "report findings first please.\n"
    )
    out = apply_operator_zero_nag_surface(raw)
    assert "once access is in place" not in out.lower()
    assert "report findings first" not in out.lower()
    assert "register a repo path" not in out.lower()


def test_format_access_reply_compact_when_operator_zero_nag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_zero_nag=True),
    )
    acc = ExternalExecutionAccess(
        dev_workspace_registered=False,
        host_executor_enabled=False,
        railway_token_present=False,
        railway_cli_on_path=False,
        github_token_configured=False,
    )
    txt = format_external_execution_access_reply(acc, user_text="check railway logs")
    low = txt.lower()
    assert "once access is in place" not in low
    assert "railway_token" in low or "railway_api_token" in low
    assert "not loaded in this worker" in low


def test_should_gate_false_when_operator_zero_nag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_zero_nag=True),
    )
    acc = ExternalExecutionAccess(
        dev_workspace_registered=False,
        host_executor_enabled=False,
        railway_token_present=False,
        railway_cli_on_path=False,
        github_token_configured=False,
    )
    assert should_gate_external_execution("railway logs", acc) is False


def test_gateway_finalize_scrubs_nag_when_operator_zero_nag(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake = SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_zero_nag=True,
        nexa_operator_proactive_intro=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _fake)
    monkeypatch.setattr("app.services.gateway.runtime.get_settings", lambda: _fake)
    monkeypatch.setattr("app.services.operator_orchestration_intro.get_settings", lambda: _fake)
    body = "Progress ok.\n\nOnce access is in place you can retry.\n"
    out = gateway_finalize_operator_or_execution_reply(
        body,
        user_text="vercel https://x.vercel.app",
        layer="execution_loop",
    )
    assert "once access is in place" not in out.lower()
