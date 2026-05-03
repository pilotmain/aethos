"""Operator full flow — phased actions merge into operator result (mocked)."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.operator_execution_loop import try_operator_execution


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_phases_merge_when_gates_pass(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: ("### Progress\n\n→ v", {}, ["→ v"], True),
    )
    monkeypatch.setattr(
        "app.services.operator_execution_loop._append_operator_phases",
        lambda **kw: (
            ["### Phase: test\n\n**Result:** ok"],
            {"tests": {"ok": True}},
            ["Running tests"],
        ),
    )

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text="check Vercel and run pytest",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is True
    assert "Phase: test" in r.text
    assert r.evidence.get("phases", {}).get("tests", {}).get("ok") is True
