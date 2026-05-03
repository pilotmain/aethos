"""PULSE.md injection flag and ``get_pulse_context`` helper."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.operator_execution_loop import try_operator_execution
from app.services.operator_pulse import get_pulse_context, read_pulse_standing_orders


def test_get_pulse_context_truncates(tmp_path) -> None:
    long_body = "x" * 2000
    (tmp_path / "PULSE.md").write_text(long_body, encoding="utf-8")
    ctx = get_pulse_context(tmp_path, max_chars=500)
    assert "Standing orders (PULSE.md)" in ctx
    assert len(ctx) < len(long_body)


def test_read_pulse_unchanged_when_get_pulse_smaller(tmp_path) -> None:
    (tmp_path / "PULSE.md").write_text("short", encoding="utf-8")
    assert read_pulse_standing_orders(tmp_path) == "short"
    assert "short" in get_pulse_context(tmp_path, max_chars=800)


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_pulse_injection_disabled_skips_standing_orders_section(
    tmp_path, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PULSE.md").write_text("SECRET-STANDING-ORDER-UNIQUE", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(
            nexa_operator_mode=True,
            nexa_pulse_injection=False,
        ),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "vercel body",
            {},
            [],
            True,
        ),
    )
    uid = f"pulse_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text=f"check Vercel Workspace: {tmp_path}",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is True
    assert "SECRET-STANDING-ORDER-UNIQUE" not in r.text
    assert "### Standing orders (PULSE.md)" not in r.text
    assert "Reading `PULSE.md`" not in r.text
