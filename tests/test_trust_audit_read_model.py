# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P1 trust read model and stable event types."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, ensure_schema
from app.models.audit_log import AuditLog
from app.services.audit_service import audit
from app.services.trust_audit_constants import (
    ACCESS_HOST_EXECUTOR_BLOCKED,
    ACCESS_PERMISSION_USED,
    NETWORK_EXTERNAL_SEND_ALLOWED,
    NETWORK_EXTERNAL_SEND_BLOCKED,
    TRUST_DASHBOARD_CORE_EVENT_TYPES,
)
from app.services.trust_audit_read_model import (
    audit_row_to_event,
    query_trust_activity,
    summarize_trust_activity,
)


def test_trust_event_types_frozen() -> None:
    assert "access.permission.used" in TRUST_DASHBOARD_CORE_EVENT_TYPES
    assert "network.external_send.allowed" in TRUST_DASHBOARD_CORE_EVENT_TYPES
    assert "safety.enforcement.path" in TRUST_DASHBOARD_CORE_EVENT_TYPES


def test_query_trust_activity_filters_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ensure_schema()
    db = SessionLocal()
    ua = f"user_a_{uuid.uuid4().hex[:12]}"
    ub = f"user_b_{uuid.uuid4().hex[:12]}"
    try:
        audit(
            db,
            event_type=NETWORK_EXTERNAL_SEND_BLOCKED,
            actor="test",
            user_id=ua,
            message="x",
            metadata={"hostname": "example.com"},
        )
        audit(
            db,
            event_type=NETWORK_EXTERNAL_SEND_ALLOWED,
            actor="test",
            user_id=ub,
            message="y",
            metadata={},
        )
        rows = query_trust_activity(db, ua, limit=50)
        assert len(rows) == 1
        assert rows[0]["event_type"] == NETWORK_EXTERNAL_SEND_BLOCKED
        assert rows[0]["destination"] == "example.com"
        assert rows[0]["status"] == "blocked"  # TRUST_UI_STATUS_BLOCKED
    finally:
        db.close()


def test_summarize_counts_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"u_sum_{uuid.uuid4().hex[:12]}"
        old = datetime.utcnow() - timedelta(days=40)
        new = datetime.utcnow() - timedelta(hours=1)
        for ev, ts in (
            (ACCESS_PERMISSION_USED, new),
            (ACCESS_HOST_EXECUTOR_BLOCKED, new),
            (NETWORK_EXTERNAL_SEND_ALLOWED, old),
        ):
            row = AuditLog(
                user_id=uid,
                event_type=ev,
                actor="t",
                message="m",
                metadata_json={},
                created_at=ts,
            )
            db.add(row)
        db.commit()
        s = summarize_trust_activity(db, uid, window_hours=24.0, recent_limit=10)
        assert s.permission_uses == 1
        assert s.host_executor_blocks == 1
        assert s.network_send_allowed == 0
    finally:
        db.close()


def test_trust_ui_status_is_tiered() -> None:
    from app.services.trust_audit_constants import (
        TRUST_UI_STATUS_ALLOWED,
        TRUST_UI_STATUS_BLOCKED,
        TRUST_UI_STATUS_WARNING,
    )
    from app.services.trust_audit_read_model import _infer_ui_status

    assert _infer_ui_status("network.external_send.blocked", {}) == TRUST_UI_STATUS_BLOCKED
    assert _infer_ui_status("access.sensitive_egress.warning", {}) == TRUST_UI_STATUS_WARNING
    assert _infer_ui_status("access.permission.used", {}) == TRUST_UI_STATUS_ALLOWED


def test_audit_row_to_event_exposes_channel_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"u_ch_{uuid.uuid4().hex[:12]}"
        audit(
            db,
            event_type=ACCESS_PERMISSION_USED,
            actor="test",
            user_id=uid,
            message="used grant",
            metadata={
                "channel": "telegram",
                "channel_user_id": "999",
                "channel_message_id": "42",
                "channel_thread_id": None,
                "channel_chat_id": "100",
            },
        )
        rows = query_trust_activity(db, uid, limit=10)
        assert len(rows) == 1
        ev = rows[0]
        assert ev.get("channel") == "telegram"
        assert ev.get("channel_user_id") == "999"
        assert ev.get("channel_message_id") == "42"
        assert ev.get("channel_thread_id") is None
        assert ev.get("channel_chat_id") == "100"
    finally:
        db.close()


def test_audit_row_to_event_channel_null_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"u_legacy_{uuid.uuid4().hex[:12]}"
        audit(
            db,
            event_type=NETWORK_EXTERNAL_SEND_BLOCKED,
            actor="test",
            user_id=uid,
            message="x",
            metadata={"hostname": "old.example.com"},
        )
        rows = query_trust_activity(db, uid, limit=10)
        assert rows[0].get("channel") is None
        assert rows[0]["destination"] == "old.example.com"
    finally:
        db.close()


def test_audit_row_to_event_empty_metadata_safe() -> None:
    from datetime import datetime

    row = AuditLog(
        user_id="u",
        event_type=ACCESS_PERMISSION_USED,
        actor="a",
        message="m",
        metadata_json={},
        created_at=datetime.utcnow(),
    )
    ev = audit_row_to_event(row)
    assert ev.get("channel") is None
    assert ev.get("event_type") == ACCESS_PERMISSION_USED


def test_verify_trust_taxonomy_script_exits_zero() -> None:
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "verify_trust_audit_taxonomy.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
