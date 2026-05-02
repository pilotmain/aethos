"""Phase 47E — autonomy rate control."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.services.autonomy.rate_control import autonomy_rate_control
from app.models.autonomy import NexaAutonomousTask


def test_autonomy_rate_control_open_by_default(db_session) -> None:
    uid = f"rate_{uuid.uuid4().hex[:10]}"
    rc = autonomy_rate_control(db_session, uid)
    assert rc.get("allowed") is True


def test_autonomy_rate_control_blocks_when_pending_cap(db_session, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_AUTONOMY_MAX_PENDING_TASKS", "1")
    get_settings.cache_clear()
    try:
        uid = f"rate_cap_{uuid.uuid4().hex[:10]}"
        db_session.add(
            NexaAutonomousTask(
                id=str(uuid.uuid4()),
                user_id=uid,
                title="t1",
                state="pending",
                priority=1,
                auto_generated=True,
                origin="autonomy",
                goal_id=None,
                context_json="{}",
            )
        )
        db_session.add(
            NexaAutonomousTask(
                id=str(uuid.uuid4()),
                user_id=uid,
                title="t2",
                state="pending",
                priority=1,
                auto_generated=True,
                origin="autonomy",
                goal_id=None,
                context_json="{}",
            )
        )
        db_session.commit()
        rc = autonomy_rate_control(db_session, uid)
        assert rc.get("allowed") is False
        assert rc.get("reason") == "pending_queue_cap"
    finally:
        monkeypatch.delenv("NEXA_AUTONOMY_MAX_PENDING_TASKS", raising=False)
        get_settings.cache_clear()
