# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 operator mode — reply scrub and gateway confirmation bypass."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest


def test_scrub_operator_idle_loop_phrases_collapses_spam(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.external_execution_session import scrub_operator_idle_loop_phrases

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True),
    )
    spam = "\n".join(["confirm again"] * 6)
    out = scrub_operator_idle_loop_phrases(spam)
    assert out.count("confirm again") < spam.count("confirm again")


def test_scrub_operator_disabled_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.external_execution_session import scrub_operator_idle_loop_phrases

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=False),
    )
    spam = "\n".join(["confirm again"] * 6)
    assert scrub_operator_idle_loop_phrases(spam) == spam


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_maybe_auto_dev_skips_medium_confirm_when_operator_mode(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Medium-confidence dev investigation proceeds without the extra confirmation prompt."""
    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway

    class Row:
        id = "ws_only"
        name = "only"

    monkeypatch.setattr(
        "app.services.gateway.runtime.get_settings",
        lambda: SimpleNamespace(
            nexa_execution_confirm_medium=True,
            nexa_operator_mode=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.workspace.list_workspaces",
        lambda db, uid: [Row()],
    )
    monkeypatch.setattr(
        "app.services.execution_policy.should_prompt_for_dev_workspace_help",
        lambda intent, risk, raw: False,
    )
    monkeypatch.setattr(
        "app.services.execution_trigger.compute_execution_confidence",
        lambda intent, raw, memory_summary=None, workspace_count=1: "medium",
    )
    monkeypatch.setattr(
        "app.services.execution_trigger.should_auto_execute_dev",
        lambda raw, intent, workspace_count=1: True,
    )
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda raw, conversation_snapshot=None, memory_summary=None: "stuck_dev",
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.service.run_dev_mission",
        lambda *a, **k: {
            "ok": True,
            "run_id": "run_op",
            "iterations": 1,
            "tests_passed": True,
            "adapter_used": "pytest",
            "progress_messages": [],
        },
    )

    uid = f"op_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway()._maybe_auto_dev_investigation(
        gctx,
        "pytest fails importing app.main — fix the import path",
        db_session,
    )
    assert out is not None
    assert out.get("intent") == "dev_mission"
    assert "not fully confident" not in (out.get("text") or "").lower()
