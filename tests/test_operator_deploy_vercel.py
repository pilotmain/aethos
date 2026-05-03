"""Deploy Vercel path is gated."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.operator_execution_actions import deploy_vercel


def test_deploy_vercel_blocked_without_deploy_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_actions.get_settings",
        lambda: SimpleNamespace(
            nexa_operator_mode=True,
            nexa_host_executor_enabled=True,
            nexa_operator_allow_write=True,
            nexa_operator_allow_deploy=False,
        ),
    )
    r = deploy_vercel("/tmp")
    assert r.get("ok") is False
    assert r.get("error") == "operator_deploy_disabled"
