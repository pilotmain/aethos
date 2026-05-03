"""Ultra-short operator / execution replies (precise mode)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.external_execution_session import format_probe_readonly_intro
from app.services.gateway.runtime import gateway_finalize_operator_or_execution_reply
from app.services.intent_focus_filter import apply_precise_operator_response


def test_apply_precise_strips_live_progress_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_precise_short_responses=True),
    )
    body = "### Live progress\n\n→ a\n→ b\n\n---\n\n### CLI output\n\n```\nok\n```"
    out = apply_precise_operator_response(body, user_text="check vercel")
    assert "### Live progress" not in out
    assert "```" in out
    assert "ok" in out


def test_apply_precise_preserves_fenced_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_precise_short_responses=True),
    )
    body = "Intro\n\n```\nvercel whoami → user\n```"
    out = apply_precise_operator_response(body, user_text="vercel")
    assert "vercel whoami" in out


def test_apply_precise_drops_cli_missing_when_user_assumes_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_precise_short_responses=True),
    )
    body = "`vercel` not found in PATH. Run `which vercel` in your terminal on this host and retry.\n\n```\nnoop\n```"
    out = apply_precise_operator_response(
        body,
        user_text="I have everything installed on this machine",
    )
    assert "not found in path" not in out.lower()
    assert "noop" in out


def test_format_probe_ultra_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_precise_short_responses=True),
    )
    assert format_probe_readonly_intro(detected_provider="vercel") == "Running read-only probes…"


def test_gateway_finalize_skips_verbose_intro_when_precise(monkeypatch: pytest.MonkeyPatch) -> None:
    _s = SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=True,
        nexa_operator_proactive_intro=True,
        nexa_operator_zero_nag=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.gateway.runtime.get_settings", lambda: _s)
    body = "### Progress\n\n→ x\n\n---\n\nOutput here."
    out = gateway_finalize_operator_or_execution_reply(
        body,
        user_text="deploy vercel",
        layer="operator_execution",
    )
    assert "Entering operator run" not in out
    assert "inspect → diagnose" not in out.lower()
