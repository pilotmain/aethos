"""Developer autonomy mode: approval bypass only when workspace is developer + approvals off."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.agent_runtime.sessions import sessions_spawn
from app.services.runtime_capabilities import autonomy_test_mode, approvals_are_enabled


@pytest.fixture
def runtime_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "true")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _spawn_payload(uid: str) -> dict:
    return {
        "requested_by": uid,
        "goal": "Some goal that is long enough here",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "r",
                "task": "Task text that is long enough here",
            }
        ],
        "timebox_minutes": 30,
        "approval_policy": {"mode": "approval_required_for_tools"},
    }


def test_autonomy_test_mode_requires_developer_and_approvals_off(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert autonomy_test_mode() is True
        assert approvals_are_enabled() is False
    finally:
        get_settings.cache_clear()


def test_regulated_workspace_never_autonomy_test_mode_even_if_approvals_false(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert autonomy_test_mode() is False
    finally:
        get_settings.cache_clear()


def test_spawn_bypass_audits_when_autonomy_mode(runtime_env, db_session, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "false")
    monkeypatch.setenv("NEXA_HOST_EXECUTOR_ENABLED", "false")
    get_settings.cache_clear()
    uid = f"adm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    try:
        before = db_session.scalars(
            select(AuditLog).where(AuditLog.event_type == "access.permission.bypassed")
        ).all()
        n_before = len(before)
        out = sessions_spawn(db_session, user_id=uid, payload=_spawn_payload(uid))
        assert out.get("spawn_group_id", "").startswith("spawn_")
        rows = db_session.scalars(
            select(AuditLog).where(AuditLog.event_type == "access.permission.bypassed")
        ).all()
        assert len(rows) > n_before
        meta = rows[-1].metadata_json or {}
        assert meta.get("tool") == "sessions_spawn"
        assert meta.get("risk") == "dev_mode"
    finally:
        get_settings.cache_clear()


def test_spawn_still_rejects_without_executor_when_not_autonomy(
    runtime_env, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "true")
    monkeypatch.setenv("NEXA_HOST_EXECUTOR_ENABLED", "false")
    get_settings.cache_clear()
    uid = f"adm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    try:
        with pytest.raises(ValueError, match="execution backends"):
            sessions_spawn(db_session, user_id=uid, payload=_spawn_payload(uid))
    finally:
        get_settings.cache_clear()
