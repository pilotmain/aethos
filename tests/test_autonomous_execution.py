"""Phase 45A/B — autonomous executor drains pending tasks via the gateway."""

from __future__ import annotations

import json
import uuid

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask
from app.services.autonomy.executor import execute_autonomous_tasks, get_pending_tasks
from app.services.gateway.runtime import NexaGateway


def test_get_pending_tasks_ordered(db_session) -> None:
    uid = f"pex_{uuid.uuid4().hex[:8]}"
    for pr, title in ((10, "low"), (50, "high")):
        db_session.add(
            NexaAutonomousTask(
                id=str(uuid.uuid4()),
                user_id=uid,
                title=title,
                state="pending",
                priority=pr,
                auto_generated=True,
                origin="autonomy",
                context_json="{}",
            )
        )
    db_session.commit()
    rows = get_pending_tasks(db_session, uid, limit=5)
    assert [r.title for r in rows] == ["high", "low"]


def test_execute_autonomous_tasks_invokes_gateway(monkeypatch, db_session, tmp_path) -> None:
    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("NEXA_AUTONOMY_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path))
    get_settings.cache_clear()
    calls: list[tuple[str, str]] = []

    def fake_handle(self, gctx, text: str, db=None):
        calls.append((gctx.channel, text[:80]))
        return {"mode": "chat", "text": "done"}

    monkeypatch.setattr(NexaGateway, "handle_message", fake_handle)
    monkeypatch.setattr(
        "app.services.autonomy.executor.should_execute",
        lambda *a, **k: (True, "ok"),
    )

    uid = f"ex_{uuid.uuid4().hex[:10]}"
    tid = str(uuid.uuid4())
    db_session.add(
        NexaAutonomousTask(
            id=tid,
            user_id=uid,
            title="hello autonomy",
            state="pending",
            priority=80,
            auto_generated=True,
            origin="autonomy",
            context_json=json.dumps({"nexa_task": {"type": "system", "context": {}}}),
        )
    )
    db_session.commit()
    try:
        out = execute_autonomous_tasks(db_session, uid, max_tasks=3)
        assert out.get("ok") is True
        assert len(calls) == 1
        assert calls[0][0] == "autonomy"
        row = db_session.get(NexaAutonomousTask, tid)
        assert row is not None
        assert row.state == "completed"
    finally:
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        monkeypatch.delenv("NEXA_AUTONOMY_EXECUTION_ENABLED", raising=False)
        monkeypatch.delenv("NEXA_MEMORY_DIR", raising=False)
        get_settings.cache_clear()


def test_should_execute_respects_budget(monkeypatch, db_session) -> None:
    from app.services.autonomy.safety import should_execute

    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            "app.services.autonomy.safety.check_budget",
            lambda *a, **k: "token_budget_per_day",
        )
        ok, reason = should_execute(db_session, "u1")
        assert ok is False
        assert "budget" in reason
    finally:
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        get_settings.cache_clear()
