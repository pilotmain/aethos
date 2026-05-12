# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 25 — bounded dev execution loop."""

from __future__ import annotations

import subprocess

from sqlalchemy import select

from app.core.security import get_valid_web_user_id
from app.main import app
from app.models.dev_runtime import NexaDevStep
from app.services.dev_runtime.service import run_dev_mission
from fastapi.testclient import TestClient


def test_loop_stops_when_tests_pass(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "loop_ok"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"loop_ok_{__import__('uuid').uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def always_pass(_repo):
        return {"ok": True, "summary": "tests passed", "parsed": {}, "command_result": {"ok": True}}

    monkeypatch.setattr("app.services.dev_runtime.service.run_repo_tests", always_pass)

    c = TestClient(app)
    try:
        w = c.post(
            "/api/v1/dev/workspaces",
            headers={"X-User-Id": uid},
            json={"name": "l", "repo_path": str(repo)},
        )
        wid = w.json()["workspace"]["id"]
        r = c.post(
            "/api/v1/dev/runs",
            headers={"X-User-Id": uid},
            json={
                "workspace_id": wid,
                "goal": "go",
                "preferred_agent": "local_stub",
                "max_iterations": 5,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("tests_passed") is True
        assert body.get("iterations") == 1
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()


def test_loop_respects_max_iterations_without_pass(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "loop_fail"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"loop_mx_{__import__('uuid').uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def always_fail(_repo):
        return {
            "ok": False,
            "summary": "FAILED tests/test_x.py::t - assert 0",
            "parsed": {"failure_count": 1},
            "command_result": {"ok": False},
        }

    monkeypatch.setattr("app.services.dev_runtime.service.run_repo_tests", always_fail)

    c = TestClient(app)
    try:
        w = c.post(
            "/api/v1/dev/workspaces",
            headers={"X-User-Id": uid},
            json={"name": "l", "repo_path": str(repo)},
        )
        wid = w.json()["workspace"]["id"]
        r = c.post(
            "/api/v1/dev/runs",
            headers={"X-User-Id": uid},
            json={
                "workspace_id": wid,
                "goal": "go",
                "preferred_agent": "local_stub",
                "max_iterations": 2,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("tests_passed") is False
        assert body.get("iterations") == 2
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()


def test_adapter_failure_stops_loop(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "loop_adapt"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"loop_ad_{__import__('uuid').uuid4().hex[:10]}"
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class Boom:
        name = "local_stub"

        def available(self):
            return True

        def run(self, request):
            from app.services.dev_runtime.coding_agents.base import CodingAgentResult

            return CodingAgentResult(
                ok=False,
                provider="local_stub",
                summary="",
                changed_files=[],
                commands_run=[],
                error="boom",
            )

    def _choose_stub(_pref=None, *, user_id=None, task_goal=None):
        return Boom()

    monkeypatch.setattr("app.services.dev_runtime.service.choose_adapter", _choose_stub)

    wid = __import__("uuid").uuid4().hex[:12]
    from app.models.dev_runtime import NexaDevWorkspace

    db_session.add(
        NexaDevWorkspace(
            id=wid,
            user_id=uid,
            name="x",
            repo_path=str(repo),
            status="ready",
        )
    )
    db_session.commit()

    out = run_dev_mission(
        db_session,
        uid,
        wid,
        "goal",
        preferred_agent="local_stub",
        max_iterations=5,
    )
    assert out.get("ok") is True
    assert out.get("tests_passed") is False
    assert out.get("has_runtime_errors") is True
    assert out.get("iterations") == 1

    monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
    get_settings.cache_clear()


def test_every_iteration_creates_step(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "loop_steps"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"loop_st_{__import__('uuid').uuid4().hex[:10]}"
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def fail_twice_then_pass(repo):
        fail_twice_then_pass.n += 1  # type: ignore[attr-defined]
        if fail_twice_then_pass.n < 3:
            return {"ok": False, "summary": "fail", "parsed": {}, "command_result": {"ok": False}}
        return {"ok": True, "summary": "ok", "parsed": {}, "command_result": {"ok": True}}

    fail_twice_then_pass.n = 0  # type: ignore[attr-defined]
    monkeypatch.setattr("app.services.dev_runtime.service.run_repo_tests", fail_twice_then_pass)

    wid = __import__("uuid").uuid4().hex[:12]
    from app.models.dev_runtime import NexaDevWorkspace

    db_session.add(
        NexaDevWorkspace(id=wid, user_id=uid, name="x", repo_path=str(repo), status="ready")
    )
    db_session.commit()

    out = run_dev_mission(db_session, uid, wid, "g", preferred_agent="local_stub", max_iterations=5)
    rid = out["run_id"]
    rows = list(db_session.scalars(select(NexaDevStep).where(NexaDevStep.run_id == rid)).all())
    loop_rows = [x for x in rows if x.step_type == "loop_iteration"]
    assert len(loop_rows) == 3
    assert all(x.iteration is not None for x in loop_rows)

    monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
    get_settings.cache_clear()
