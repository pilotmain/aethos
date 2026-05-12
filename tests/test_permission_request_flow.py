# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Chat-first permission requests for host executor (unified format + resume)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.agent_job import AgentJob
from app.models.conversation_context import ConversationContext
from app.services import access_permissions as ap
from app.services import next_action_apply as naa
from app.services.permission_request_flow import (
    find_pending_permission_duplicate,
    is_missing_grant_error,
    is_permission_eligible_precheck_failure,
    request_permission_from_chat,
)
from app.services.workspace_registry import add_root


def _settings_for_perm_tests(work_root: str) -> SimpleNamespace:
    return SimpleNamespace(
        nexa_host_executor_enabled=True,
        nexa_access_permissions_enforced=True,
        nexa_workspace_strict=False,
        host_executor_work_root=work_root,
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
    )


@pytest.fixture
def perm_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Real get_settings() is used by autonomy_test_mode() — pin regulated + approvals so permission UX tests are deterministic.
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"perm_flow_{uuid.uuid4().hex[:16]}"
        try:
            add_root(db, uid, root)
        except ValueError:
            pass
        yield db, root, uid
    finally:
        db.close()
        get_settings.cache_clear()


@patch("app.core.config.get_settings")
def test_request_permission_from_chat_reuses_pending(
    mock_gs, perm_tmp: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root, uid = perm_tmp
    mock_gs.return_value = _settings_for_perm_tests(root)
    monkeypatch.chdir(root)

    msg1, row1, reused1 = request_permission_from_chat(
        db,
        uid,
        scope=ap.SCOPE_FILE_READ,
        target=root,
        risk_level=ap.RISK_LOW,
        reason="test",
    )
    assert not reused1
    assert "Permission required" in msg1 or "permission" in msg1.lower()
    msg2, row2, reused2 = request_permission_from_chat(
        db,
        uid,
        scope=ap.SCOPE_FILE_READ,
        target=root,
        risk_level=ap.RISK_LOW,
        reason="test",
    )
    assert reused2
    assert row1.id == row2.id
    assert "already pending" in msg2.lower()


def test_find_pending_duplicate_matches_scope_target(perm_tmp: tuple) -> None:
    db, root, uid = perm_tmp
    row = ap.request_permission(
        db,
        uid,
        scope=ap.SCOPE_FILE_READ,
        target=root,
        risk_level=ap.RISK_LOW,
        reason="x",
    )
    dup = find_pending_permission_duplicate(
        db, uid, scope=ap.SCOPE_FILE_READ, target=root
    )
    assert dup is not None and dup.id == row.id


def test_is_missing_grant_error() -> None:
    assert is_missing_grant_error("No granted permission for scope=x")
    assert not is_missing_grant_error("workspace policy blocked")


def test_is_permission_eligible_precheck_failure_abs_targets() -> None:
    payload = {"nexa_permission_abs_targets": ["/tmp/foo"]}
    assert is_permission_eligible_precheck_failure(
        "path outside registered workspace roots — use /workspace add",
        payload,
    )
    assert not is_permission_eligible_precheck_failure(
        "path outside registered workspace roots — use /workspace add",
        {},
    )


@patch("app.services.next_action_apply.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.host_executor_chat.get_settings")
def test_chat_triggers_permission_blocked_then_duplicate_message(
    mock_hx_gs,
    mock_pr_gs,
    mock_wr_gs,
    mock_naa_gs,
    perm_tmp: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root, uid = perm_tmp
    s = _settings_for_perm_tests(root)
    mock_hx_gs.return_value = s
    mock_pr_gs.return_value = s
    mock_wr_gs.return_value = s
    mock_naa_gs.return_value = s
    monkeypatch.chdir(root)

    cctx = ConversationContext(user_id=uid, session_id="default", recent_messages_json="[]")
    db.add(cctx)
    db.commit()
    c2 = db.get(ConversationContext, cctx.id) or cctx

    r1 = naa.apply_next_action_to_user_text(db, c2, "run tests", web_session_id="ws-perm")
    assert r1.early_assistant and (
        "permission" in r1.early_assistant.lower()
        or "🔐" in r1.early_assistant
    )
    db.refresh(c2)
    assert (c2.blocked_host_executor_json or "").strip()

    r2 = naa.apply_next_action_to_user_text(db, c2, "run tests", web_session_id="ws-perm")
    assert r2.early_assistant and "already pending" in (r2.early_assistant or "").lower()

    jobs_n = db.query(AgentJob).filter(AgentJob.user_id == uid).count()
    assert jobs_n == 0


@patch("app.services.next_action_apply.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.host_executor_chat.get_settings")
def test_grant_then_continue_sets_host_pending_then_queues(
    mock_hx_gs,
    mock_pr_gs,
    mock_wr_gs,
    mock_naa_gs,
    perm_tmp: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root, uid = perm_tmp
    s = _settings_for_perm_tests(root)
    mock_hx_gs.return_value = s
    mock_pr_gs.return_value = s
    mock_wr_gs.return_value = s
    mock_naa_gs.return_value = s
    monkeypatch.chdir(root)

    cctx = ConversationContext(user_id=uid, session_id="default", recent_messages_json="[]")
    db.add(cctx)
    db.commit()
    c2 = db.get(ConversationContext, cctx.id) or cctx

    r1 = naa.apply_next_action_to_user_text(db, c2, "run tests", web_session_id="ws-grant")
    assert r1.early_assistant and "Permission required" in r1.early_assistant
    assert r1.permission_required
    db.refresh(c2)
    raw_b = c2.blocked_host_executor_json or "{}"
    blocked = json.loads(raw_b)
    pid = int(blocked["permission_id"])
    gr = ap.grant_permission(db, uid, pid, granted_by_user_id=uid)
    assert gr is not None

    r2 = naa.apply_next_action_to_user_text(db, c2, "continue", web_session_id="ws-grant")
    assert r2.early_assistant and "host executor" in (r2.early_assistant or "").lower()
    db.refresh(c2)
    assert c2.next_action_pending_inject_json and "host_executor" in c2.next_action_pending_inject_json
    assert not (c2.blocked_host_executor_json or "").strip()

    r3 = naa.apply_next_action_to_user_text(db, c2, "yes", web_session_id="ws-grant")
    assert r3.early_assistant and "Queued local action" in r3.early_assistant
    job = db.query(AgentJob).filter(AgentJob.user_id == uid).order_by(AgentJob.id.desc()).first()
    assert job is not None


@patch("app.services.next_action_apply.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.host_executor_chat.get_settings")
def test_denied_permission_clears_blocked_with_fallback(
    mock_hx_gs,
    mock_pr_gs,
    mock_wr_gs,
    mock_naa_gs,
    perm_tmp: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root, uid = perm_tmp
    s = _settings_for_perm_tests(root)
    mock_hx_gs.return_value = s
    mock_pr_gs.return_value = s
    mock_wr_gs.return_value = s
    mock_naa_gs.return_value = s
    monkeypatch.chdir(root)

    cctx = ConversationContext(user_id=uid, session_id="default", recent_messages_json="[]")
    db.add(cctx)
    db.commit()
    c2 = db.get(ConversationContext, cctx.id) or cctx

    r1 = naa.apply_next_action_to_user_text(db, c2, "run tests", web_session_id="ws-deny")
    db.refresh(c2)
    raw_b = c2.blocked_host_executor_json or "{}"
    pid = int(json.loads(raw_b)["permission_id"])
    ap.deny_permission(db, uid, pid)

    r2 = naa.apply_next_action_to_user_text(db, c2, "continue", web_session_id="ws-deny")
    assert r2.early_assistant
    low = (r2.early_assistant or "").lower()
    assert "did not access" in low or "won't access" in low or "wont access" in low
    db.refresh(c2)
    assert not (c2.blocked_host_executor_json or "").strip()
