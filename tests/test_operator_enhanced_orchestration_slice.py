"""Slice tests for enhanced orchestration: proactive intro + PULSE.md surfacing."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.operator_execution_loop import try_operator_execution
from app.services.operator_orchestration_intro import maybe_prepend_operator_orchestration_intro
from app.services.operator_pulse import format_pulse_section, read_pulse_standing_orders


def test_maybe_prepend_intro_skipped_when_operator_mode_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_orchestration_intro.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=False),
    )
    body = "### Progress\n\nx"
    out = maybe_prepend_operator_orchestration_intro(
        body,
        user_text="deploy to Vercel",
        orchestration_source="operator_execution",
    )
    assert out == body


def test_maybe_prepend_intro_when_operator_mode_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_orchestration_intro.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True, nexa_operator_proactive_intro=True),
    )
    body = "### Progress\n\nx"
    out = maybe_prepend_operator_orchestration_intro(
        body,
        user_text="deploy my app to Vercel production",
        orchestration_source="operator_execution",
    )
    assert out.startswith("**Understood.**")
    assert "operator-style run" in out
    assert "### Progress" in out


def test_maybe_prepend_intro_respects_proactive_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_orchestration_intro.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True, nexa_operator_proactive_intro=False),
    )
    body = "### Progress\n\nx"
    out = maybe_prepend_operator_orchestration_intro(
        body,
        user_text="x",
        orchestration_source="execution_loop",
    )
    assert out == body


def test_read_pulse_standing_orders(tmp_path) -> None:
    assert read_pulse_standing_orders(None) is None
    assert read_pulse_standing_orders(tmp_path) is None
    (tmp_path / "PULSE.md").write_text("  keep main green  \n", encoding="utf-8")
    got = read_pulse_standing_orders(tmp_path)
    assert got == "keep main green"


def test_format_pulse_section() -> None:
    assert "Standing orders" in format_pulse_section("hello")


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_loop_appends_pulse_when_workspace_resolved(tmp_path, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "PULSE.md").write_text("Run `npm test` before every push.", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "### Progress\n\n→ stub\n\nvercel ok",
            {"provider": "vercel"},
            ["Starting Vercel investigation"],
            True,
        ),
    )

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text=f"check Vercel deploy status Workspace: {tmp_path}",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is True
    assert "Standing orders (PULSE.md)" in r.text
    assert "npm test" in r.text


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_prepends_intro_for_operator_reply(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    _op_settings = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_proactive_intro=True,
    )
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: _op_settings,
    )
    monkeypatch.setattr(
        "app.services.operator_orchestration_intro.get_settings",
        lambda: _op_settings,
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "### Progress\n\n→ x\n",
            {},
            [],
            True,
        ),
    )

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(gctx, "tail Vercel logs for my-app.vercel.app", db=db_session)
    text = out.get("text") or ""
    assert "**Understood.**" in text
    assert "### Progress" in text
