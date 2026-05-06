"""Permission registry + workspace policy for host executor (auditable, scoped)."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy import func, select

from app.core.db import SessionLocal, ensure_schema
from app.models.access_permission import AccessPermission
from app.models.audit_log import AuditLog
from app.services import access_permissions as ap
from app.services import host_executor
from app.services.workspace_registry import add_root


def _register_workspace(db, uid: str, root: str) -> None:
    """Tests run under /tmp paths; register that root so policy allows it."""
    try:
        add_root(db, uid, root)
    except ValueError:
        pass


def test_request_permission_creates_pending() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        row = ap.request_permission(
            db,
            "perm_req_user",
            scope=ap.SCOPE_FILE_READ,
            target="/tmp/nexa-test-root",
            risk_level=ap.RISK_LOW,
            reason="unit test",
        )
        assert row.status == ap.STATUS_PENDING
        assert row.scope == ap.SCOPE_FILE_READ
    finally:
        db.close()


def test_grant_allows_path_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_grant_user"
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_PROJECT_SCAN,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        gr = ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)
        assert gr is not None
        ok, err = ap.has_permission_for_paths(
            db,
            uid,
            ap.SCOPE_PROJECT_SCAN,
            [tmp_path.resolve()],
            ap.RISK_LOW,
        )
        assert ok, err
    finally:
        db.close()


def test_grant_covers_out_of_tree_path_before_workspace_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Approved grant for an explicit target must win over default-work-root policy (e.g. Docker /app)."""
    monkeypatch.chdir(tmp_path)
    dw = tmp_path / "narrow_default_root"
    dw.mkdir()
    outside = tmp_path / "explicit_grant_target"
    outside.mkdir()
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "grant_out_tree_user"
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_PROJECT_SCAN,
            target=str(outside.resolve()),
            risk_level=ap.RISK_LOW,
            reason="explicit target",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)

        def fake_dw() -> Path:
            return dw.resolve()

        with patch("app.services.workspace_registry.default_work_root_path", fake_dw):
            ok, err = ap.has_permission_for_paths(
                db,
                uid,
                ap.SCOPE_PROJECT_SCAN,
                [outside.resolve()],
                ap.RISK_LOW,
            )
            assert ok, err
    finally:
        db.close()


def test_revoke_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_revoke_user"
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_FILE_READ,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)
        ap.revoke_permission(db, uid, pend.id)
        ok, err = ap.has_permission_for_paths(
            db,
            uid,
            ap.SCOPE_FILE_READ,
            [tmp_path.resolve()],
            ap.RISK_LOW,
        )
        assert not ok
        assert "no granted permission" in err.lower()
    finally:
        db.close()


def test_strict_workspace_without_roots_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_strict_user"
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_FILE_READ,
            target=root,
            risk_level=ap.RISK_HIGH,
            reason="test",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)

        class StrictOn:
            nexa_workspace_strict = True

        with patch("app.services.workspace_registry.get_settings", return_value=StrictOn()):
            ok, err = ap.has_permission_for_paths(
                db,
                uid,
                ap.SCOPE_FILE_READ,
                [tmp_path.resolve()],
                ap.RISK_HIGH,
            )
        assert not ok
        assert "workspace" in err.lower()
    finally:
        db.close()


def test_sensitive_read_requires_high_grant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "foo.env").write_text("x=y\n", encoding="utf-8")
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_sens_user"
        root = str(tmp_path.resolve())
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_FILE_READ,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)
        sens_path = (tmp_path / "foo.env").resolve()
        ok, err = ap.has_permission_for_paths(
            db,
            uid,
            ap.SCOPE_FILE_READ,
            [sens_path],
            ap.RISK_HIGH,
        )
        assert not ok
        assert "risk" in err.lower() or "permission" in err.lower()
    finally:
        db.close()


def test_audit_blocked_host_executor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "audit_block_user"
        job = MagicMock()
        job.user_id = uid
        before = db.scalar(select(func.count()).select_from(AuditLog)) or 0

        class S:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = str(tmp_path)
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        with patch.object(host_executor, "get_settings", return_value=S()):
            with pytest.raises(ValueError, match="permission|workspace|registered"):
                host_executor.execute_payload({"host_action": "git_status"}, db=db, job=job)

        after = db.scalar(select(func.count()).select_from(AuditLog)) or 0
        assert after > before
    finally:
        db.close()


def test_enforced_execute_succeeds_with_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
        env={
            **dict(__import__("os").environ),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )

    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_ok_exec_user"
        root = str(tmp_path.resolve())
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_GIT_OPERATIONS,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)

        job = MagicMock()
        job.user_id = uid

        class S:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = str(tmp_path)
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        with patch.object(host_executor, "get_settings", return_value=S()):
            out = host_executor.execute_payload({"host_action": "git_status"}, db=db, job=job)
        assert "README" in out or "main" in out.lower() or "master" in out.lower()
        assert "🔐" in out or "Using permission" in out
    finally:
        db.close()


def test_permission_request_prompt_copy() -> None:
    txt = ap.format_permission_request_prompt(
        scope=ap.SCOPE_FILE_READ,
        target="/Users/x/proj",
        risk_level=ap.RISK_LOW,
        reason="unit",
    )
    assert "🔐" in txt and "Permission required" in txt
    assert "Allow once" not in txt and "Target:" not in txt


def test_resolve_paths_prefers_nexa_permission_abs_targets(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    wr = tmp_path.resolve()
    p = {
        "host_action": "list_directory",
        "relative_path": ".",
        "nexa_permission_abs_targets": [str(nested.resolve())],
    }
    out = ap.resolve_host_executor_permission_paths(wr, p)
    assert out == [nested.resolve()]


def test_permission_denied_fallback_copy() -> None:
    msg = ap.permission_denied_fallback_message().lower()
    assert "denied" in msg and "path" in msg


def test_finalize_updates_last_used_and_audits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_last_used_u"
        root = str(tmp_path.resolve())
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_GIT_OPERATIONS,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)

        job = MagicMock()
        job.user_id = uid

        class S:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = str(tmp_path)
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        before_audit = db.scalar(select(func.count()).select_from(AuditLog)) or 0
        with patch.object(host_executor, "get_settings", return_value=S()):
            host_executor.execute_payload(
                {
                    "host_action": "git_status",
                    "nexa_permission_abs_targets": [root],
                },
                db=db,
                job=job,
            )
        db.expire_all()
        row = db.get(AccessPermission, pend.id)
        assert row is not None and row.last_used_at is not None
        after_audit = db.scalar(select(func.count()).select_from(AuditLog)) or 0
        assert after_audit > before_audit
    finally:
        db.close()


def test_once_grant_consumed_after_host_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_once_u"
        root = str(tmp_path.resolve())
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_GIT_OPERATIONS,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        ap.grant_permission(
            db, uid, pend.id, granted_by_user_id=uid, grant_mode=ap.GRANT_MODE_ONCE
        )

        job = MagicMock()
        job.user_id = uid

        class S:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = str(tmp_path)
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        with patch.object(host_executor, "get_settings", return_value=S()):
            host_executor.execute_payload({"host_action": "git_status"}, db=db, job=job)
        row = db.get(AccessPermission, pend.id)
        assert row is not None and row.status == ap.STATUS_CONSUMED

        with patch.object(host_executor, "get_settings", return_value=S()):
            with pytest.raises(ValueError, match="no granted permission|permission"):
                host_executor.execute_payload({"host_action": "git_status"}, db=db, job=job)
    finally:
        db.close()


def test_session_expired_blocks_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "perm_sess_exp_u"
        root = str(tmp_path.resolve())
        _register_workspace(db, uid, root)
        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_GIT_OPERATIONS,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="test",
        )
        row = ap.grant_permission(
            db,
            uid,
            pend.id,
            granted_by_user_id=uid,
            grant_mode=ap.GRANT_MODE_SESSION,
            grant_session_hours=8.0,
        )
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(row)
        db.commit()

        job = MagicMock()
        job.user_id = uid

        class S:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = str(tmp_path)
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        with patch.object(host_executor, "get_settings", return_value=S()):
            with pytest.raises(ValueError, match="no granted permission|permission"):
                host_executor.execute_payload({"host_action": "git_status"}, db=db, job=job)
    finally:
        db.close()
