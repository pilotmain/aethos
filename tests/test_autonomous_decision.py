# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 44A/B — autonomous decision loop persists prioritized tasks and decision logs."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask, NexaAutonomyDecisionLog
from app.models.dev_runtime import NexaDevRun
from app.services.autonomy.decision import autonomous_decision_loop


def test_decision_loop_skips_without_mode(monkeypatch, db_session) -> None:
    out = autonomous_decision_loop(db_session, user_id="u1")
    assert out.get("skipped") is True


def test_decision_loop_enqueues_on_failed_dev_run(monkeypatch, db_session) -> None:
    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    get_settings.cache_clear()
    try:
        uid = f"auto_dec_{uuid.uuid4().hex[:10]}"
        run = NexaDevRun(
            id=f"dr_{uuid.uuid4().hex[:12]}",
            user_id=uid,
            workspace_id="ws1",
            goal="x",
            status="failed",
            error="tests failed",
        )
        db_session.add(run)
        db_session.commit()

        out = autonomous_decision_loop(db_session, user_id=uid)
        assert out.get("ok") is True
        assert out.get("generated_task_ids")
        rows = list(db_session.scalars(select(NexaAutonomousTask).where(NexaAutonomousTask.user_id == uid)).all())
        assert len(rows) >= 1
        logs = list(
            db_session.scalars(select(NexaAutonomyDecisionLog).where(NexaAutonomyDecisionLog.user_id == uid)).all()
        )
        assert len(logs) >= 1
    finally:
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        get_settings.cache_clear()
