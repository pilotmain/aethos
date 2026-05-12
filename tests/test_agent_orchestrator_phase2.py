# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2: assignment ↔ permission lifecycle, host bridge, Mission Control fields, chat guard."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.models.access_permission import AccessPermission
from app.models.agent_job import AgentJob
from app.models.agent_team import AgentAssignment, AgentOrganization
from app.models.user import User
from app.models.user_agent import UserAgent
from app.services import access_permissions as ap
from app.services.agent_team.chat import try_agent_team_chat_turn
from app.services.agent_team.service import (
    DuplicateAssignmentError,
    create_assignment,
    dispatch_assignment,
    get_or_create_default_organization,
    list_assignments_for_user,
)
from app.services.content_provenance import InstructionSource, apply_trusted_instruction_source
from app.services.mission_control.read_model import build_mission_control_dashboard
from app.services.nexa_safety_policy import stamp_host_payload
from app.services.permission_request_flow import (
    request_permission_from_chat,
    validate_host_payload_paths_before_permission,
)
from app.services.permission_resume_execution import resume_host_executor_after_grant
from app.services.response_sanitizer import sanitize_execution_and_assignment_reply
from app.services.workspace_registry import add_root


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _settings_perm(root: str) -> SimpleNamespace:
    return SimpleNamespace(
        nexa_host_executor_enabled=True,
        nexa_access_permissions_enforced=True,
        nexa_workspace_strict=False,
        host_executor_work_root=root,
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
    )


def test_precheck_assignment_host_user_message_rejects_bad_path(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.agent_team import host_bridge

    monkeypatch.setattr(
        host_bridge,
        "infer_host_payload_for_assignment_text",
        lambda *a, **k: {
            "host_action": "read_multiple_files",
            "nexa_permission_abs_targets": ["/___nexa_phase2_missing_abs___"],
        },
    )
    ok, err = host_bridge.precheck_assignment_host_user_message(
        db_session, user_id="u1", user_message="read stuff", web_session_id=None
    )
    assert ok is False
    assert err and "does not exist" in err.lower()


def test_explicit_assign_does_not_create_row_when_precheck_fails(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.agent_team.chat.precheck_assignment_host_user_message",
        lambda *_a, **_k: (False, "Path does not exist: /bad"),
    )
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    get_or_create_default_organization(db_session, uid)
    before = db_session.query(AgentAssignment).filter(AgentAssignment.user_id == uid).count()
    out = try_agent_team_chat_turn(
        db_session,
        uid,
        "assign @research-analyst to read /nope/file.txt",
        web_session_id=None,
    )
    after = db_session.query(AgentAssignment).filter(AgentAssignment.user_id == uid).count()
    assert after == before
    assert out is not None
    assert "not created" in out.reply.lower()


def test_validate_host_payload_rejects_missing_abs_path(db_session, tmp_path: Path) -> None:
    missing = tmp_path / "nope_dir_never_exists_xyz"
    pl = {
        "host_action": "read_multiple_files",
        "nexa_permission_abs_targets": [str(missing.resolve())],
    }
    ok, err = validate_host_payload_paths_before_permission(pl)
    assert ok is False
    assert err and "does not exist" in err.lower()


def test_permission_from_chat_metadata_has_assignment_ids(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    captured: dict = {}

    def _capture_request_permission(db, owner_user_id, **kwargs):
        captured.update(kwargs.get("metadata") or {})
        row = AccessPermission(
            owner_user_id=owner_user_id[:64],
            scope="test_scope",
            target="/tmp",
            risk_level="low",
            status="pending",
            metadata_json=dict(kwargs.get("metadata") or {}),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    monkeypatch.setattr(
        "app.services.permission_request_flow.request_permission",
        _capture_request_permission,
    )

    request_permission_from_chat(
        db_session,
        uid,
        scope="test_scope",
        target="/tmp",
        risk_level="low",
        reason="r",
        assignment_id=42,
        assigned_to_handle="research-analyst",
    )
    assert captured.get("assignment_id") == 42
    assert captured.get("agent_assignment_id") == 42
    assert captured.get("assigned_to_handle") == "research-analyst"


def test_dispatch_waiting_approval_skips_llm(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    db_session.add(
        UserAgent(
            owner_user_id=uid,
            agent_key="research_analyst",
            display_name="RA",
            description="",
            system_prompt="You are helpful.",
        )
    )
    db_session.commit()

    calls: list[str] = []

    def _fake_host(db, *, row, uid):
        row.status = "waiting_approval"
        row.input_json = {**(row.input_json or {}), "pending_permission_id": 501}
        db.add(row)
        db.commit()
        return {
            "ok": True,
            "waiting_approval": True,
            "permission_required": {"type": "permission_required", "permission_request_id": "501"},
            "assignment_id": row.id,
            "message": "Approve to continue.",
        }

    def _no_llm(*_a, **_k):
        calls.append("llm")
        return "should not run"

    monkeypatch.setattr(
        "app.services.agent_team.service.try_assignment_host_dispatch",
        _fake_host,
    )
    monkeypatch.setattr(
        "app.services.agent_team.service.run_custom_user_agent",
        _no_llm,
    )

    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="research_analyst",
        title="Read files",
        description="Read files under project",
        organization_id=org.id,
        input_json={"user_message": "read ./README.md"},
    )
    out = dispatch_assignment(db_session, assignment_id=row.id, user_id=uid)
    assert out.get("waiting_approval") is True
    assert calls == []
    db_session.refresh(row)
    assert row.status == "waiting_approval"


@patch("app.services.permission_resume_execution.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.host_executor_chat.get_settings")
def test_resume_after_grant_updates_agent_assignment(
    mock_hx_gs,
    mock_pr_gs,
    mock_wr_gs,
    mock_resume_gs,
    db_session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    try:
        add_root(db_session, uid, root)
    except ValueError:
        pass

    s = _settings_perm(root)
    mock_hx_gs.return_value = s
    mock_pr_gs.return_value = s
    mock_wr_gs.return_value = s
    mock_resume_gs.return_value = s

    org = AgentOrganization(user_id=uid, name="Org", enabled=True)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    assign = AgentAssignment(
        user_id=uid,
        organization_id=org.id,
        assigned_to_handle="research_analyst",
        assigned_by_handle="user",
        title="list",
        description="list",
        status="waiting_approval",
        input_json={"pending_permission_id": 1},
    )
    db_session.add(assign)
    db_session.commit()
    db_session.refresh(assign)

    stamped = stamp_host_payload(
        apply_trusted_instruction_source(
            {
                "host_action": "list_directory",
                "relative_path": ".",
                "agent_assignment_id": assign.id,
            },
            InstructionSource.USER_MESSAGE.value,
        )
    )
    perm_row = ap.request_permission(
        db_session,
        uid,
        scope=ap.SCOPE_PROJECT_SCAN,
        target=root,
        risk_level=ap.RISK_LOW,
        reason="list",
        metadata={
            "pending_payload": stamped,
            "pending_title": "List",
            "web_session_id": "sess-p2",
            "assignment_id": assign.id,
            "agent_assignment_id": assign.id,
            "source": "test",
        },
    )

    ap.grant_permission(
        db_session,
        uid,
        perm_row.id,
        granted_by_user_id=uid,
        grant_mode=ap.GRANT_MODE_ONCE,
    )

    jid = resume_host_executor_after_grant(db_session, uid, perm_row.id, web_session_id="sess-p2")
    job = db_session.get(AgentJob, jid)
    assert job is not None

    db_session.refresh(assign)
    assert assign.status == "running"
    assert (assign.output_json or {}).get("host_job_id") == jid
    assert "pending_permission_id" not in (assign.input_json or {})


def test_mission_control_lists_assignment_status(db_session) -> None:
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="x",
        title="t",
        description="d",
        organization_id=org.id,
        input_json={},
    )
    row.status = "waiting_approval"
    db_session.add(row)
    db_session.commit()

    summary = build_mission_control_dashboard(db_session, uid, hours=24)
    orch = summary.get("orchestration") or {}
    assigns = orch.get("assignments") or []
    assert isinstance(assigns, list) and assigns
    hit = next((a for a in assigns if int(a.get("id") or 0) == row.id), None)
    assert hit is not None
    assert hit.get("status") == "waiting_approval"
    assert hit.get("assigned_to_handle") == "x"
    assert hit.get("title") == "t"


def test_list_assignments_includes_core_fields(db_session) -> None:
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="y",
        title="Title line",
        description="d",
        organization_id=org.id,
        input_json={},
    )
    rows = list_assignments_for_user(db_session, uid, limit=5)
    assert any(r["id"] == row.id for r in rows)
    one = next(r for r in rows if r["id"] == row.id)
    assert one["status"] == row.status
    assert one["title"] == "Title line"


def test_fake_async_guard_replaces_vague_reply() -> None:
    raw = "I'm working on it — almost done!"
    fixed = sanitize_execution_and_assignment_reply(
        raw,
        user_text="assign @foo to read the docs",
        related_job_ids=[],
        permission_required=None,
    )
    assert "assignment" in fixed.lower()
    assert fixed != raw
    fixed2 = sanitize_execution_and_assignment_reply(
        raw,
        user_text="assign @foo to read the docs",
        related_job_ids=[99],
        permission_required=None,
    )
    assert fixed2 == raw


def test_create_assignment_duplicate_raises(db_session) -> None:
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="research_analyst",
        title="Duplicate title check",
        description="d",
        organization_id=org.id,
        input_json={},
    )
    with pytest.raises(DuplicateAssignmentError):
        create_assignment(
            db_session,
            user_id=uid,
            assigned_to_handle="research_analyst",
            title="Duplicate title check",
            description="d2",
            organization_id=org.id,
            input_json={},
        )


def test_duplicate_explicit_assign_chat_message(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.agent_team.chat.precheck_assignment_host_user_message",
        lambda *_a, **_k: (True, None),
    )

    def _keep_running_dispatch(db, assignment_id, user_id):
        row = db_session.get(AgentAssignment, int(assignment_id))
        if row:
            row.status = "running"
            db_session.add(row)
            db_session.commit()
        return {"ok": True, "output": {"text": "stub"}, "host_job_id": 999}

    monkeypatch.setattr(
        "app.services.agent_team.chat.dispatch_assignment",
        _keep_running_dispatch,
    )
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    get_or_create_default_organization(db_session, uid)
    instr = "do the unique duplicate-test task xyz123"
    first = try_agent_team_chat_turn(
        db_session,
        uid,
        f"assign @research-analyst to {instr}",
        web_session_id=None,
    )
    second = try_agent_team_chat_turn(
        db_session,
        uid,
        f"assign @research-analyst to {instr}",
        web_session_id=None,
    )
    assert first is not None and second is not None
    assert "not created" in second.reply.lower() or "already" in second.reply.lower()


def test_agent_working_on_deterministic_reply(db_session) -> None:
    uid = f"p2_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="research_analyst",
        title="R task",
        description="d",
        organization_id=org.id,
        input_json={},
    )
    out = try_agent_team_chat_turn(
        db_session,
        uid,
        "what is @research-analyst working on?",
        web_session_id=None,
    )
    assert out is not None
    assert "r task" in out.reply.lower() or "#" in out.reply
