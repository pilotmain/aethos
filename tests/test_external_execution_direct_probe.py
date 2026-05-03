"""P0 — direct probe without awaiting-followup session (same bounded runner)."""

from __future__ import annotations

from app.services.conversation_context_service import get_or_create_context
from app.services.external_execution_runner import BoundedRailwayInvestigation
from app.services.external_execution_session import maybe_start_external_probe_from_turn
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def test_maybe_start_probe_when_railway_local_auth_and_permission(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="host_executor_disabled"),
    )

    uid = "u-direct-probe"
    cctx = get_or_create_context(db_session, uid)

    out = maybe_start_external_probe_from_turn(
        db_session,
        uid,
        "I am already logged into Railway locally, try for yourself",
        cctx,
        conversation_snapshot=None,
    )
    assert out is not None
    txt = out.get("text") or ""
    assert "railway whoami" in txt.lower()
    assert "host execution is disabled" in txt.lower()


def test_maybe_start_returns_none_without_railway_context(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="no_workspace"),
    )
    uid = "u-no-ctx"
    cctx = get_or_create_context(db_session, uid)
    out = maybe_start_external_probe_from_turn(
        db_session,
        uid,
        "already authenticated, try for yourself",
        cctx,
        conversation_snapshot=None,
    )
    assert out is None


def test_maybe_start_suppressed_when_awaiting_followup(db_session, monkeypatch) -> None:
    """Resume path owns awaiting-followup state."""
    import json as json_lib

    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="no_workspace"),
    )

    uid = "u-await"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = json_lib.dumps(
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

    out = maybe_start_external_probe_from_turn(
        db_session,
        uid,
        "I am already logged into Railway locally, try for yourself",
        cctx,
        conversation_snapshot=None,
    )
    assert out is None


def test_gateway_handle_full_chat_runs_direct_probe(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="host_executor_disabled"),
    )

    uid = "u-gw-probe"
    gctx = GatewayContext(user_id=uid, channel="web")
    gw = NexaGateway()
    payload = gw.handle_full_chat(
        gctx,
        "already authenticated — try for yourself. railway.",
        db=db_session,
    )
    assert payload.get("intent") == "external_execution_continue"
    assert "host execution is disabled" in (payload.get("text") or "").lower()
