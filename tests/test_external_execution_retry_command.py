"""P0 — explicit retry phrases run bounded Railway/repo investigation."""

from __future__ import annotations

import json

import pytest

from app.services.conversation_context_service import get_or_create_context
from app.services.external_execution_access import ExternalExecutionAccess
from app.services.external_execution_runner import BoundedRailwayInvestigation
from app.services.external_execution_session import (
    is_retry_external_execution,
    try_retry_external_execution_turn,
)
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.fixture
def railway_worker_access_ok(monkeypatch):
    """Retry tests assume CLI or env token exists unless explicitly testing the blocker."""
    fake = ExternalExecutionAccess(
        dev_workspace_registered=True,
        host_executor_enabled=True,
        railway_token_present=True,
        railway_cli_on_path=True,
        github_token_configured=False,
    )
    monkeypatch.setattr(
        "app.services.external_execution_access.assess_external_execution_access",
        lambda db, uid: fake,
    )


def test_is_retry_external_execution_phrases() -> None:
    assert is_retry_external_execution("retry external execution")
    assert is_retry_external_execution("Retry External Execution.")
    assert is_retry_external_execution("continue railway investigation")
    assert not is_retry_external_execution("fix my railway deploy")


def test_retry_runs_runner_when_completed_flow_exists(db_session, monkeypatch, railway_worker_access_ok) -> None:
    captured: list[dict] = []

    def fake_run(_db, uid, collected):
        captured.append(dict(collected))
        return BoundedRailwayInvestigation(skipped_reason="host_executor_disabled")

    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        fake_run,
    )

    uid = "u-retry-done"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = json.dumps(
        {
            "external_execution": {
                "status": "completed",
                "collected": {"auth_method": "local_cli", "deploy_mode": "report_then_approve"},
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }
    )
    db_session.add(cctx)
    db_session.commit()

    out = try_retry_external_execution_turn(db_session, uid, "retry external execution", cctx)
    assert out is not None
    text = out["text"] or ""
    assert "retrying railway investigation" in text.lower()
    assert "railway whoami" in text.lower()
    assert "railway status" in text.lower()
    assert "recorded — say retry" not in text.lower()
    assert captured and captured[0].get("auth_method") == "local_cli"


def test_retry_no_saved_flow(db_session) -> None:
    uid = "u-retry-none"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = None
    db_session.add(cctx)
    db_session.commit()

    out = try_retry_external_execution_turn(db_session, uid, "retry external execution", cctx)
    assert out is not None
    assert "don't have a saved railway investigation" in (out.get("text") or "").lower()


def test_gateway_retry_invokes_runner(monkeypatch, db_session, railway_worker_access_ok) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="host_executor_disabled"),
    )

    uid = "u-gw-retry"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = json.dumps(
        {
            "external_execution": {
                "status": "awaiting_followup",
                "collected": {},
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }
    )
    db_session.add(cctx)
    db_session.commit()

    gctx = GatewayContext(user_id=uid, channel="web")
    gw = NexaGateway()
    payload = gw.handle_full_chat(gctx, "retry external execution", db=db_session)
    assert payload.get("intent") == "external_execution_continue"
    body = (payload.get("text") or "").lower()
    assert "retrying railway investigation" in body
    assert "recorded — say retry" not in body
