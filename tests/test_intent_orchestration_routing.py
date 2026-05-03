"""Orchestration / external infra intents — do not downgrade to local file path UX."""

from __future__ import annotations

from app.services.intent_classifier import (
    get_intent,
    looks_like_external_execution,
    looks_like_external_investigation,
    looks_like_orchestrate_system,
)
from app.services.legacy_behavior_utils import Context, build_response
from app.services.local_file_intent import infer_local_file_request


def test_orchestrate_system_intent_triggers() -> None:
    assert looks_like_orchestrate_system("Check Mission Control and report what succeeded vs failed")
    assert get_intent("Act as orchestrator and summarize active work") == "orchestrate_system"


def test_external_investigation_intent_triggers() -> None:
    assert looks_like_external_investigation("Railway worker keeps crashing after deploy")
    assert get_intent("Why is my Railway service unhealthy") == "external_investigation"


def test_external_execution_pipeline_overrides_investigation() -> None:
    msg = "Can you check Railway, fix repo, push, redeploy, and report?"
    assert looks_like_external_execution(msg)
    assert not looks_like_external_investigation(msg)
    assert get_intent(msg) == "external_execution"


def test_external_investigation_diagnosis_not_external_execution() -> None:
    assert not looks_like_external_execution("Why is my Railway service unhealthy")


def test_infer_local_file_skips_when_orchestrating() -> None:
    lf = infer_local_file_request(
        "Please check Mission Control and tell me what failed on Railway",
        default_relative_base=".",
    )
    assert lf.matched is False


def test_infer_local_file_skips_external_execution_pipeline() -> None:
    lf = infer_local_file_request(
        "Check Railway, fix repo, push, redeploy",
        default_relative_base=".",
    )
    assert lf.matched is False


def test_orchestrate_wins_over_external_when_both_cues() -> None:
    assert (
        get_intent("Mission Control says Railway failed — what happened?") == "orchestrate_system"
    )


def test_build_response_external_execution_gates_without_access() -> None:
    ctx = Context(user_id="u", tasks=[], last_plan=[], memory={})
    r = build_response(
        "Check Railway, fix repo, push, redeploy",
        "external_execution",
        ctx,
        db=None,
        app_user_id=None,
    )
    assert "coordinate" in r.lower() or "access" in r.lower()
    assert "Nexa" in r


def test_build_response_external_execution_runs_read_only_probe_when_not_gated(
    db_session, monkeypatch
) -> None:
    from app.services.external_execution_access import ExternalExecutionAccess
    from app.services.external_execution_runner import BoundedRailwayInvestigation

    monkeypatch.setattr(
        "app.services.external_execution_access.should_gate_external_execution",
        lambda *_a, **_k: False,
    )
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
        lambda *_a, **_k: BoundedRailwayInvestigation(skipped_reason="host_executor_disabled"),
    )
    monkeypatch.setattr(
        "app.services.external_execution_runner.format_investigation_for_chat",
        lambda inv: "PROBE_VERIFY_BLOCK",
    )
    monkeypatch.setattr(
        "app.services.orchestrator_status_reply.format_orchestrator_mc_snapshot",
        lambda db, uid: "",
    )
    monkeypatch.setattr(
        "app.services.external_execution_session.mark_external_execution_awaiting_followup",
        lambda *a, **k: None,
    )

    ctx = Context(user_id="u-probe", tasks=[], last_plan=[], memory={})
    r = build_response(
        "Check Railway, fix repo, push, redeploy",
        "external_execution",
        ctx,
        db=db_session,
        app_user_id="u-probe",
    )
    assert "read-only probe" in r.lower()
    assert "PROBE_VERIFY_BLOCK" in r
