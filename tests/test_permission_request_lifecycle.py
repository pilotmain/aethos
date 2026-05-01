"""End-to-end permission request: store payload, grant, resume enqueue, once consumption (P0)."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.access_permission import AccessPermission
from app.models.agent_job import AgentJob
from app.services import access_permissions as ap
from app.services import next_action_apply as naa
from app.models.conversation_context import ConversationContext
from app.services.content_provenance import InstructionSource, apply_trusted_instruction_source
from app.services.nexa_safety_policy import stamp_host_payload
from app.services.permission_resume_execution import PermissionResumeError, resume_host_executor_after_grant
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
def perm_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"plf_{uuid.uuid4().hex[:16]}"
        try:
            add_root(db, uid, root)
        except ValueError:
            pass
        yield db, root, uid
    finally:
        db.close()
        get_settings.cache_clear()


@patch("app.services.next_action_apply.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.host_executor_chat.get_settings")
def test_first_message_includes_permission_required_struct(
    mock_hx_gs,
    mock_pr_gs,
    mock_wr_gs,
    mock_naa_gs,
    perm_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root, uid = perm_env
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

    r1 = naa.apply_next_action_to_user_text(db, c2, "run tests", web_session_id="pr-1")
    assert r1.permission_required
    assert r1.permission_required.get("type") == "permission_required"
    assert "permission_request_id" in r1.permission_required
    assistant_blob = (r1.early_assistant or "").lower()
    assert "allow once" not in assistant_blob
    assert "allow for session" not in assistant_blob
    assert "system -> permissions" not in assistant_blob.replace("→", "->")


@patch("app.services.permission_resume_execution.get_settings")
@patch("app.services.workspace_registry.get_settings")
@patch("app.services.permission_request_flow.get_settings")
@patch("app.services.host_executor_chat.get_settings")
def test_apis_grants_and_resume_enqueues_job(
    mock_hx_gs,
    mock_pr_gs,
    mock_wr_gs,
    mock_resume_gs,
    perm_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, root, uid = perm_env
    s = _settings_for_perm_tests(root)
    mock_hx_gs.return_value = s
    mock_pr_gs.return_value = s
    mock_wr_gs.return_value = s
    mock_resume_gs.return_value = s
    monkeypatch.chdir(root)

    stamped = stamp_host_payload(
        apply_trusted_instruction_source(
            {"host_action": "list_directory", "relative_path": "."},
            InstructionSource.USER_MESSAGE.value,
        )
    )
    row = ap.request_permission(
        db,
        uid,
        scope=ap.SCOPE_PROJECT_SCAN,
        target=root,
        risk_level=ap.RISK_LOW,
        reason="list",
        metadata={
            "pending_payload": stamped,
            "pending_title": "List dir",
            "web_session_id": "sess-api",
            "source": "test",
        },
    )

    gp = ap.grant_permission(
        db,
        uid,
        row.id,
        granted_by_user_id=uid,
        grant_mode=ap.GRANT_MODE_ONCE,
    )
    assert gp is not None

    jid = resume_host_executor_after_grant(db, uid, row.id, web_session_id="sess-api")
    job = db.query(AgentJob).filter(AgentJob.user_id == uid).order_by(AgentJob.id.desc()).first()
    assert job is not None and job.id == jid
    assert (job.status or "").lower() == "queued"
    assert job.approval_required is False
    refreshed = db.get(AccessPermission, row.id)
    assert refreshed is not None
    assert "pending_payload" not in (refreshed.metadata_json or {})


def test_resume_without_pending_payload_errors(perm_env) -> None:
    db, root, uid = perm_env
    row = ap.request_permission(
        db,
        uid,
        scope=ap.SCOPE_PROJECT_SCAN,
        target=root,
        risk_level=ap.RISK_LOW,
        reason="x",
        metadata={},
    )
    ap.grant_permission(db, uid, row.id, granted_by_user_id=uid, grant_mode=ap.GRANT_MODE_ONCE)
    with pytest.raises(PermissionResumeError):
        resume_host_executor_after_grant(db, uid, row.id)


@patch("app.services.local_file_intent.get_settings")
def test_list_files_in_resolves_to_list_directory(mock_gs, perm_env, monkeypatch: pytest.MonkeyPatch):
    from app.services.local_file_intent import infer_local_file_request

    db, root, uid = perm_env
    mock_gs.return_value = SimpleNamespace(host_executor_work_root=root)
    monkeypatch.chdir(Path(root))

    lf = infer_local_file_request(f"list files in {root}", default_relative_base=".")
    assert lf.matched and lf.payload
    assert lf.payload.get("host_action") == "list_directory"
