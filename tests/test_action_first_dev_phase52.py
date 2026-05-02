"""Phase 52B — auto dev investigation policy."""

from __future__ import annotations

import pytest

from app.services.execution_policy import should_auto_run_dev_task


def test_auto_run_when_single_workspace_low_risk_stuck_dev() -> None:
    assert should_auto_run_dev_task("stuck_dev", "low", 1, "pytest fails after auth change")


def test_no_auto_when_multiple_workspaces() -> None:
    assert not should_auto_run_dev_task("stuck_dev", "low", 2, "tests failing")


def test_no_auto_when_user_asks_explain_only() -> None:
    assert not should_auto_run_dev_task(
        "stuck_dev", "low", 1, "just explain why pytest fails, do not run anything"
    )


def test_no_auto_when_high_risk_text() -> None:
    assert not should_auto_run_dev_task(
        "stuck_dev", "high", 1, "rm -rf / on production deploy"
    )


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_auto_dev_calls_run_when_policy_allows(
    monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean
) -> None:
    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway

    monkeypatch.setattr(
        NexaGateway,
        "_maybe_auto_dev_investigation",
        lambda self, gctx, text, db: {
            "mode": "chat",
            "text": "Dev run stub.",
            "intent": "dev_mission",
        },
    )
    ctx = GatewayContext(user_id="auto_dev_u1", channel="web", extras={"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "pytest fails", db=nexa_runtime_clean)
    assert out.get("text") == "Dev run stub."
