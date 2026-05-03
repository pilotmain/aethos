"""P0 — follow-up turns recognize local CLI auth + permission to run read-only probes."""

from __future__ import annotations

import json

from app.services.conversation_context_service import get_or_create_context
from app.services.external_execution_runner import BoundedRailwayInvestigation
from app.services.external_execution_session import parse_followup_preferences, try_resume_external_execution_turn


def test_parse_followup_already_authenticated_try_yourself_sets_cli_and_probe() -> None:
    out = parse_followup_preferences("already authenticated, try for yourself", {})
    assert out.get("auth_method") == "local_cli"
    assert out.get("permission_to_probe") is True
    assert out.get("deploy_mode") == "report_then_approve"


def test_parse_followup_logged_in_locally_use_railway_cli() -> None:
    out = parse_followup_preferences("logged in locally, use railway cli", {})
    assert out.get("auth_method") == "local_cli"


def test_resume_already_authenticated_runs_bounded_runner(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_session._workspace_repo_hint",
        lambda _db, _uid: "/tmp/demo-repo",
    )

    captured: list[dict] = []

    def fake_run(_db, uid, collected):
        captured.append(dict(collected))
        inv = BoundedRailwayInvestigation(skipped_reason="host_executor_disabled")
        inv.deploy_blocked_by_policy = True
        inv.policy_note = "_policy_"
        return inv

    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        fake_run,
    )

    uid = "u-local-auth"
    cctx = get_or_create_context(db_session, uid)
    st = {
        "external_execution": {
            "status": "awaiting_followup",
            "collected": {},
            "updated_at": "2099-01-01T00:00:00+00:00",
        }
    }
    cctx.current_flow_state_json = json.dumps(st)
    db_session.add(cctx)
    db_session.commit()

    out = try_resume_external_execution_turn(
        db_session,
        uid,
        "already authenticated, just try for yourself",
        cctx,
    )
    assert out is not None
    text = out.get("text") or ""
    assert "railway whoami" in text.lower()
    assert "railway status" in text.lower()
    assert "railway logs" in text.lower()
    assert "git status" in text.lower()
    assert "i cannot log in" not in text.lower()
    assert "paste the output" not in text.lower()

    assert captured and captured[0].get("auth_method") == "local_cli"
    assert captured[0].get("permission_to_probe") is True
