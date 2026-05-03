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
        lambda: __import__("types").SimpleNamespace(
            nexa_operator_mode=True,
            nexa_operator_proactive_intro=True,
            nexa_operator_precise_short_responses=False,
        ),
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
    _s = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.operator_execution_loop.get_settings", lambda: _s)
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
        nexa_operator_precise_short_responses=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _op_settings)
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
    assert "### Live progress" in text
    assert text.count("**Understood.**") == 1


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_no_intro_when_proactive_disabled(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    _op_settings = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_proactive_intro=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _op_settings)
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
    assert "**Understood.**" not in (out.get("text") or "")


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_pulse_reread_each_operator_turn(tmp_path, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "PULSE.md").write_text("alpha-standing-order", encoding="utf-8")
    _s = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.operator_execution_loop.get_settings", lambda: _s)
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "vercel body",
            {},
            [],
            True,
        ),
    )
    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r1 = try_operator_execution(
        user_text=f"check Vercel Workspace: {tmp_path}",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert "alpha-standing-order" in r1.text
    (tmp_path / "PULSE.md").write_text("beta-replaced-content", encoding="utf-8")
    r2 = try_operator_execution(
        user_text=f"check Vercel Workspace: {tmp_path}",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert "beta-replaced-content" in r2.text
    assert "alpha-standing-order" not in r2.text


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_live_progress_ordering_before_pulse_body(tmp_path, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "PULSE.md").write_text("orders", encoding="utf-8")
    _s = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.operator_execution_loop.get_settings", lambda: _s)
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "vercel section",
            {},
            [],
            True,
        ),
    )
    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text=f"Vercel status Workspace: {tmp_path}",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    t = r.text
    assert "### Live progress" in t
    lp = t.index("### Live progress")
    pulse_read = t.index("Reading `PULSE.md`")
    standing = t.index("### Standing orders (PULSE.md)")
    assert lp < pulse_read < standing


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_pulse_skips_deploy_when_forbidden(tmp_path, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "PULSE.md").write_text("Do not deploy to production without CFO sign-off.\n", encoding="utf-8")
    _s = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.operator_execution_loop.get_settings", lambda: _s)
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "vercel",
            {},
            [],
            True,
        ),
    )
    deploy_calls: list[str] = []

    def _no_deploy(*_a, **_k):
        deploy_calls.append("deploy")
        return {"ok": True, "stdout": ""}

    monkeypatch.setattr("app.services.operator_execution_actions.deploy_vercel", _no_deploy)
    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text=f"deploy to Vercel Workspace: {tmp_path}",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is True
    assert deploy_calls == []
    assert "Skipped" in r.text or "skipped" in r.text.lower()
    assert r.verified is True


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_no_mission_complete_footer_when_verify_not_healthy(tmp_path, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    _s = __import__("types").SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.operator_execution_loop.get_settings", lambda: _s)
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "vercel",
            {},
            [],
            True,
        ),
    )

    def _fake_deploy(*_a, **_k):
        return {"ok": True, "returncode": 0, "stdout": "deployed", "stderr": ""}

    def _fake_verify(*_a, **_k):
        return {"ok": False, "status_code": 502, "url": "https://x.vercel.app", "error": "Bad Gateway"}

    monkeypatch.setattr("app.services.operator_execution_actions.deploy_vercel", _fake_deploy)
    monkeypatch.setattr("app.services.operator_execution_actions.verify_http_head", _fake_verify)

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    msg = (
        f"deploy to Vercel and verify production Workspace: {tmp_path} "
        "Production URL: https://x.vercel.app"
    )
    r = try_operator_execution(user_text=msg, gctx=gctx, db=db_session, snapshot={})
    assert r.handled is True
    assert r.verified is False
    assert "**Mission complete.**" not in r.text
    assert "502" in r.text or "failed" in r.text.lower()
