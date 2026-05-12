# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execution-layer permission reply guard (stale LLM / System → Permissions)."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.conversation_context import ConversationContext
from app.services.permission_reply_guard import (
    patch_llm_reply_for_permission_execution_layer,
    permission_required_payload_from_blocked_host_json,
    reply_contains_stale_permission_guidance,
    user_message_suggests_privileged_host_action,
)
from app.services.workspace_registry import add_root


def _settings_perm(tmp_root: str) -> SimpleNamespace:
    return SimpleNamespace(
        nexa_host_executor_enabled=True,
        nexa_access_permissions_enforced=True,
        nexa_workspace_strict=False,
        host_executor_work_root=tmp_root,
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
    )


@pytest.fixture
def guard_perm_env(tmp_path_factory, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "true")
    get_settings.cache_clear()
    tmp_path = tmp_path_factory.mktemp("guard_perm")
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    uid = f"grd_{uuid.uuid4().hex[:16]}"
    try:
        try:
            add_root(db, uid, root)
        except ValueError:
            pass
        yield db, root, uid
    finally:
        db.close()
        get_settings.cache_clear()


def test_stale_substring_detection() -> None:
    assert reply_contains_stale_permission_guidance("Go to System → Permissions to fix this")
    assert reply_contains_stale_permission_guidance("I already told you to open /permissions")
    assert reply_contains_stale_permission_guidance("Click Allow once to proceed")
    assert not reply_contains_stale_permission_guidance("Here is the file list you asked for.")


def test_privileged_user_text_heuristic() -> None:
    assert user_message_suggests_privileged_host_action("list files in /Users/example/lifeos")
    assert not user_message_suggests_privileged_host_action("Thanks, that helps")


def test_guard_strips_fetch_promise_when_message_is_privileged() -> None:
    class _C:
        pass

    r, p, rk, it = patch_llm_reply_for_permission_execution_layer(
        None,  # type: ignore[arg-type]
        _C(),
        web_session_id="default",
        user_text="list files in /Users/x/y",
        reply="Got it — let me fetch that listing for you now.",
    )
    assert p is None and rk is None
    assert "fetch" not in r.lower()


@patch("app.services.host_executor_chat.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.local_file_intent.get_settings")
def test_guard_second_chance_returns_permission_payload(
    mock_lf_gs,
    mock_wr_gs,
    mock_pr_gs,
    mock_hx_gs,
    guard_perm_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root, uid = guard_perm_env
    s = _settings_perm(root)
    mock_lf_gs.return_value = s
    mock_wr_gs.return_value = s
    mock_pr_gs.return_value = s
    mock_hx_gs.return_value = s
    monkeypatch.chdir(root)

    cctx = ConversationContext(user_id=uid, session_id="default", recent_messages_json="[]")
    db.add(cctx)
    db.commit()

    outside_dir = Path(root).resolve().parent / "nexa_guard_perm_outside"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside = str(outside_dir)
    try:
        r, p, rk, _it = patch_llm_reply_for_permission_execution_layer(
            db,
            cctx,
            web_session_id="default",
            user_text=f"list files in {outside}",
            reply="Got it — let me fetch that listing for you now.",
        )
    finally:
        try:
            outside_dir.rmdir()
        except OSError:
            pass
    assert p is not None
    assert p.get("type") == "permission_required"
    assert rk == "permission_required"
    assert "fetch" not in r.lower()


def test_blocked_host_json_round_trips_permission_card_payload() -> None:
    class _Ctx:
        blocked_host_executor_json = """{"payload":{"host_action":"list_directory","relative_path":"."},"title":"List","permission_id":42}"""

    p = permission_required_payload_from_blocked_host_json(_Ctx())
    assert p is not None
    assert p.get("permission_request_id") == "42"


def test_guard_replaces_stale_reply_without_db() -> None:
    class _C:
        pass

    r, p, rk, it = patch_llm_reply_for_permission_execution_layer(
        None,  # type: ignore[arg-type]
        _C(),
        web_session_id="default",
        user_text="Thanks",
        reply="You need to go to System → Permissions and add a root first.",
    )
    assert p is None
    assert "Permission required" in r
    assert "Allow once" not in r
