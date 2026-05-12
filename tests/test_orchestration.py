# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 16a — orchestration policy, REST delegate auth, gateway parse."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.orchestration.policy import OrchestrationPolicy, parse_gateway_delegate, validate_handles


def test_parse_gateway_delegate_basic():
    r = parse_gateway_delegate("/delegate @git-a @git-b Fix the bug")
    assert r is not None
    agents, goal, parallel = r
    assert "git_a" in agents and "git_b" in agents
    assert "Fix the bug" in goal
    assert parallel is False


def test_parse_gateway_delegate_parallel():
    r = parse_gateway_delegate("/delegate parallel @a @b do thing")
    assert r is not None
    _, _, parallel = r
    assert parallel is True


def test_parse_gateway_delegate_not_command():
    assert parse_gateway_delegate("hello @a @b") is None


def test_validate_handles_cap():
    pol = OrchestrationPolicy(max_delegates=2, max_parallel=2, timeout_ms=5000, require_approval=False)
    ok, err = validate_handles(["a", "b", "c"], policy=pol)
    assert ok == []
    assert err and "max 2" in err.lower()


def test_api_delegate_unauthorized():
    app.dependency_overrides.pop(get_valid_web_user_id, None)
    try:
        with TestClient(app) as c:
            r = c.post(
                "/api/v1/orchestration/delegate",
                json={"agents": ["x", "y"], "goal": "g"},
            )
            assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_api_delegate_mocked(api_client, monkeypatch):
    def fake_run(db, user_id, agents, goal, **kw):  # noqa: ARG001
        return {
            "ok": True,
            "spawn_group_id": "sg1",
            "assignment_ids": [1, 2],
            "results": [
                {"ok": True, "assignment_id": 1, "output": {"text": "done1"}},
                {"ok": True, "assignment_id": 2, "output": {"text": "done2"}},
            ],
            "parallel": False,
        }

    monkeypatch.setattr("app.api.routes.orchestration.run_delegation", fake_run)
    client, uid = api_client
    r = client.post(
        "/api/v1/orchestration/delegate",
        headers={"X-User-Id": uid},
        json={"agents": ["agent_a", "agent_b"], "goal": "test goal"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["spawn_group_id"] == "sg1"
