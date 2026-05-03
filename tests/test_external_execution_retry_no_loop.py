"""P0 — retry response must not instruct the user to repeat the same phrase in a tight loop."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_behavior_utils_does_not_echo_recorded_retry_parrot() -> None:
    """Regression: prior copy repeated **retry external execution** inside a ‘Recorded — …’ loop."""
    src = (_REPO_ROOT / "app/services/legacy_behavior_utils.py").read_text(encoding="utf-8")
    assert "Recorded — say **retry external execution**" not in src


def test_retry_gateway_response_not_instruction_loop(monkeypatch, db_session) -> None:
    from app.services.conversation_context_service import get_or_create_context
    from app.services.external_execution_access import ExternalExecutionAccess
    from app.services.external_execution_runner import BoundedRailwayInvestigation
    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway
    import json

    monkeypatch.setattr(
        "app.services.external_execution_access.assess_external_execution_access",
        lambda db, uid: ExternalExecutionAccess(
            dev_workspace_registered=True,
            host_executor_enabled=True,
            railway_token_present=True,
            railway_cli_on_path=True,
            github_token_configured=False,
        ),
    )
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="no_workspace"),
    )

    uid = "u-no-loop"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = json.dumps(
        {
            "external_execution": {
                "status": "completed",
                "collected": {"auth_method": "local_cli"},
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }
    )
    db_session.add(cctx)
    db_session.commit()

    payload = NexaGateway().handle_full_chat(
        GatewayContext(user_id=uid, channel="web"),
        "retry external execution",
        db=db_session,
    )
    body = payload.get("text") or ""
    lower = body.lower()
    assert "recorded — say retry external execution" not in lower
    assert "say **retry external execution** or paste" not in lower
