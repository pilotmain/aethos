"""Phase 39 — parallel agent waves."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.workers.loop import run_parallel_agents


def test_run_parallel_agents_respects_depends_on(monkeypatch) -> None:
    calls: list[str] = []

    def fake_single(agent, db, *, deadline):
        calls.append(agent["handle"])
        agent["output"] = {"ok": True}
        return True

    monkeypatch.setattr("app.services.workers.loop._use_parallel_waves", lambda: False)
    monkeypatch.setattr("app.services.workers.loop._run_single_agent", fake_single)

    agents = [
        {"handle": "a", "status": "queued", "depends_on": [], "mission_id": "m"},
        {"handle": "b", "status": "queued", "depends_on": ["a"], "mission_id": "m"},
    ]
    db = MagicMock()
    completed: set[str] = set()

    w1 = run_parallel_agents(agents, db, completed=completed, deadline=None)
    assert "a" in w1
    completed.update(w1)
    w2 = run_parallel_agents(agents, db, completed=completed, deadline=None)
    assert "b" in w2
