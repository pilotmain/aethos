# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 67 — POST /agent-assignments auto-runs dispatch_assignment when payload omits ``auto_dispatch``."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.core.security import get_valid_web_user_id
from app.main import app
from app.models.user import User
from app.services.agent_team.service import get_or_create_default_organization


@pytest.fixture
def fresh_uid() -> str:
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"ad_{uuid.uuid4().hex[:12]}"
        db.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
        db.commit()
        get_or_create_default_organization(db, uid)
        return uid
    finally:
        db.close()


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


def _stub_dispatch(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]) -> None:
    def _record(_db: Any, *, assignment_id: int, user_id: str) -> dict[str, Any]:
        out = {"ok": True, "assignment_id": assignment_id, "output": {"text": "stub"}}
        calls.append({"assignment_id": assignment_id, "user_id": user_id})
        return out

    monkeypatch.setattr(
        "app.api.routes.agent_organization.dispatch_assignment", _record, raising=True
    )


def test_post_agent_assignments_auto_dispatch_runs_immediately(
    fresh_uid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    _stub_dispatch(monkeypatch, calls)
    _override_user(fresh_uid)
    try:
        client = TestClient(app)
        r = client.post(
            "/api/v1/agent-assignments",
            json={
                "assigned_to_handle": "research-analyst",
                "title": "phase67 auto run",
                "description": "summarize the market",
                "priority": "normal",
                "input_json": {},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "id" in body
        assert isinstance(body.get("auto_dispatch"), dict)
        assert body["auto_dispatch"].get("ok") is True
        assert len(calls) == 1
        assert calls[0]["assignment_id"] == body["id"]
    finally:
        app.dependency_overrides.clear()


def test_post_agent_assignments_explicit_false_does_not_dispatch(
    fresh_uid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    _stub_dispatch(monkeypatch, calls)
    _override_user(fresh_uid)
    try:
        client = TestClient(app)
        r = client.post(
            "/api/v1/agent-assignments",
            json={
                "assigned_to_handle": "research-analyst",
                "title": "phase67 manual",
                "description": "x",
                "priority": "normal",
                "input_json": {},
                "auto_dispatch": False,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "auto_dispatch" not in body
        assert calls == []
    finally:
        app.dependency_overrides.clear()


def test_post_agent_assignments_settings_default_off(
    fresh_uid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    _stub_dispatch(monkeypatch, calls)

    s = get_settings()
    monkeypatch.setattr(s, "nexa_assignment_auto_dispatch_default", False, raising=False)

    _override_user(fresh_uid)
    try:
        client = TestClient(app)
        r = client.post(
            "/api/v1/agent-assignments",
            json={
                "assigned_to_handle": "research-analyst",
                "title": "phase67 default-off",
                "description": "x",
                "priority": "normal",
                "input_json": {},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "auto_dispatch" not in body
        assert calls == []
    finally:
        app.dependency_overrides.clear()


def test_post_agent_assignments_dispatch_failure_returns_persisted_row(
    fresh_uid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(
        "app.api.routes.agent_organization.dispatch_assignment", _boom, raising=True
    )
    _override_user(fresh_uid)
    try:
        client = TestClient(app)
        r = client.post(
            "/api/v1/agent-assignments",
            json={
                "assigned_to_handle": "research-analyst",
                "title": "phase67 boom",
                "description": "x",
                "priority": "normal",
                "input_json": {},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "id" in body
        assert body.get("auto_dispatch", {}).get("ok") is False
        assert body["auto_dispatch"].get("error") == "dispatch_failed"
    finally:
        app.dependency_overrides.clear()


def test_post_agent_assignments_duplicate_still_returns_409(
    fresh_uid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-dispatch path must not bypass the existing duplicate-detection 409."""
    calls: list[dict[str, Any]] = []
    _stub_dispatch(monkeypatch, calls)
    _override_user(fresh_uid)
    try:
        client = TestClient(app)
        body = {
            "assigned_to_handle": "research-analyst",
            "title": "phase67 dedupe",
            "description": "x",
            "priority": "normal",
            "input_json": {},
            "auto_dispatch": False,
        }
        r1 = client.post("/api/v1/agent-assignments", json=body)
        assert r1.status_code == 200, r1.text
        r2 = client.post("/api/v1/agent-assignments", json=body)
        assert r2.status_code == 409, r2.text
        detail = r2.json().get("detail") or {}
        assert detail.get("error") == "duplicate_assignment"
        assert calls == []
    finally:
        app.dependency_overrides.clear()
