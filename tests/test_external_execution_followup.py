"""External execution session — user can reply after access/prompt without dead-ending."""

from __future__ import annotations

import json

from app.services.conversation_context_service import get_or_create_context
from app.services.external_execution_session import (
    mark_external_execution_awaiting_followup,
    parse_followup_preferences,
    try_resume_external_execution_turn,
)
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def test_parse_followup_preferences_detects_cli_and_report_first() -> None:
    raw = "logged in locally\nReport findings first, then ask before deploying"
    out = parse_followup_preferences(raw, {})
    assert out.get("auth_method") == "local_cli"
    assert out.get("deploy_mode") == "report_then_approve"


def test_try_resume_returns_ack_when_awaiting(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_session._workspace_repo_hint",
        lambda _db, _uid: "/tmp/demo-repo",
    )
    uid = "u-ext-exec"
    cctx = get_or_create_context(db_session, uid)
    st = {"external_execution": {"status": "awaiting_followup", "collected": {}, "updated_at": "2099-01-01T00:00:00+00:00"}}
    cctx.current_flow_state_json = json.dumps(st)
    db_session.add(cctx)
    db_session.commit()

    out = try_resume_external_execution_turn(
        db_session,
        uid,
        "logged in locally\nreport findings first",
        cctx,
    )
    assert out is not None
    assert out["intent"] == "external_execution_continue"
    assert "Got it" in (out.get("text") or "")
    assert "not" in (out.get("text") or "").lower() or "report" in (out.get("text") or "").lower()

    db_session.refresh(cctx)
    frag = json.loads(cctx.current_flow_state_json or "{}").get("external_execution") or {}
    assert frag.get("status") == "completed"


def test_gateway_handle_full_chat_resumes_external_execution(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_session._workspace_repo_hint",
        lambda _db, _uid: None,
    )
    uid = "u-gateway-ex"
    cctx = get_or_create_context(db_session, uid)
    st = {"external_execution": {"status": "awaiting_followup", "collected": {}, "updated_at": "2099-01-01T00:00:00+00:00"}}
    cctx.current_flow_state_json = json.dumps(st)
    db_session.add(cctx)
    db_session.commit()

    gctx = GatewayContext(user_id=uid, channel="web")
    gw = NexaGateway()
    payload = gw.handle_full_chat(gctx, "CLI locally. Report first before deploy.", db=db_session)
    assert (payload.get("text") or "").strip()
    assert payload.get("intent") == "external_execution_continue"


def test_mark_awaiting_sets_fragment(db_session) -> None:
    uid = "u-mark"
    cctx = get_or_create_context(db_session, uid)
    mark_external_execution_awaiting_followup(db_session, uid, cctx, gated=True)
    db_session.refresh(cctx)
    st = json.loads(cctx.current_flow_state_json or "{}")
    assert st.get("external_execution", {}).get("status") == "awaiting_followup"
