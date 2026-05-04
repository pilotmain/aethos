"""Operator execution loop — gateway wiring and provider selection."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.operator_execution_loop import (
    _try_enqueue_readme_push_chain_after_github,
    try_operator_execution,
)


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_loop_skipped_when_mode_off(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=False),
    )
    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text="check Vercel deploy Workspace: /tmp",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is False


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_loop_handles_vercel_cue(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "### Progress\n\n→ stub\n\nvercel ok",
            {"provider": "vercel"},
            ["Starting Vercel investigation"],
            True,
        ),
    )

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text="Please check my Vercel project logs",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is True
    assert r.provider == "vercel"
    assert "stub" in r.text or "vercel" in r.text.lower()


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_operator_before_execution_loop(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "### Progress\n\n→ x\n",
            {},
            [],
            True,
        ),
    )
    calls: list[str] = []

    def boom(**kw):
        calls.append("exec_loop")
        from app.services.execution_loop import ExecutionLoopResult

        return ExecutionLoopResult(handled=False, text="")

    monkeypatch.setattr("app.services.execution_loop.try_execute_or_explain", boom)

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(gctx, "tail Vercel logs for my-app.vercel.app", db=db_session)
    assert out.get("operator_execution") is True
    assert calls == []


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_readme_push_enqueued_after_github_auth_ok(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(
        user_id=uid,
        channel="web",
        extras={"web_session_id": "sess1"},
    )
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: SimpleNamespace(
            nexa_host_executor_enabled=True,
            nexa_host_executor_chain_enabled=True,
        ),
    )

    chain_pl = {
        "host_action": "chain",
        "stop_on_failure": True,
        "actions": [
            {"host_action": "file_write", "relative_path": "README.md", "content": "# x"},
            {"host_action": "git_commit", "commit_message": "docs: readme"},
            {"host_action": "git_push"},
        ],
    }
    monkeypatch.setattr(
        "app.services.host_executor_nl_chain.try_infer_readme_push_chain_nl",
        lambda _t: chain_pl,
    )
    monkeypatch.setattr(
        "app.services.host_executor_chat._validate_enqueue_payload",
        lambda pl: pl if (pl or {}).get("host_action") == "chain" else None,
    )

    def _fake_enqueue(db, app_user_id, *, safe_pl, title, web_session_id):
        return SimpleNamespace(id=9911)

    monkeypatch.setattr(
        "app.services.host_executor_chat.enqueue_host_job_from_validated_payload",
        _fake_enqueue,
    )

    out = _try_enqueue_readme_push_chain_after_github(
        db_session,
        uid,
        "Please add a README and push to origin",
        gctx,
    )
    assert out is not None
    assert "9911" in out
    assert "queued" in out.lower()
