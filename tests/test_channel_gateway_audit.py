# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4: channel origin merged into audit/trust metadata."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.access_permission import AccessPermission
from app.models.audit_log import AuditLog
from app.services.access_permissions import (
    RISK_LOW,
    SCOPE_FILE_READ,
    request_permission,
)
from app.services.audit_service import audit
from app.services.channel_gateway.audit_integration import enrich_with_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.outbound_request_gate import gate_outbound_http_body


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine, tables=[AuditLog.__table__, AccessPermission.__table__])
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_enrich_with_channel_origin_adds_fields_when_bound() -> None:
    meta = {"instruction_source": "user"}
    with bind_channel_origin(
        {
            "channel": "telegram",
            "channel_user_id": "42",
            "channel_message_id": "7",
            "channel_thread_id": None,
            "channel_chat_id": "99",
        }
    ):
        out = enrich_with_channel_origin(meta)
    assert out["instruction_source"] == "user"
    assert out["channel"] == "telegram"
    assert out["channel_user_id"] == "42"
    assert out["channel_message_id"] == "7"
    assert "channel_thread_id" not in out  # None skipped in origin loop... wait, we only add v is not None
    assert out["channel_chat_id"] == "99"


def test_enrich_with_channel_origin_noop_without_context() -> None:
    m = {"a": 1}
    assert enrich_with_channel_origin(m) == {"a": 1}
    assert m == {"a": 1}


def test_enrich_does_not_overwrite_callers_keys() -> None:
    with bind_channel_origin({"channel": "web", "channel_user_id": "u"}):
        out = enrich_with_channel_origin({"channel": "custom", "x": 1})
    assert out["channel"] == "custom"
    assert out["x"] == 1
    assert "channel_user_id" in out and out["channel_user_id"] == "u"


def test_audit_log_includes_channel_metadata(mem_db: Session) -> None:
    with bind_channel_origin(
        {"channel": "web", "channel_user_id": "web_x", "web_session_id": "s1"}
    ):
        audit(
            mem_db,
            event_type="test.channel.lineage",
            actor="test",
            user_id="web_x",
            message="m",
            metadata={"k": 1},
        )
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("k") == 1
    assert md.get("channel") == "web"
    assert md.get("channel_user_id") == "web_x"
    assert md.get("web_session_id") == "s1"


def test_audit_without_origin_unchanged_shape(mem_db: Session) -> None:
    audit(
        mem_db,
        event_type="test.no_origin",
        actor="test",
        user_id="u1",
        message="m",
        metadata={"only": "x"},
    )
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    md = dict(row.metadata_json or {})
    assert md == {"only": "x"}


def test_permission_request_audit_includes_channel(mem_db: Session) -> None:
    with bind_channel_origin({"channel": "web", "channel_user_id": "owner1"}):
        request_permission(
            mem_db,
            "owner1",
            scope=SCOPE_FILE_READ,
            target="/tmp/nexa_test",
            risk_level=RISK_LOW,
        )
    row = mem_db.scalars(
        select(AuditLog)
        .where(AuditLog.event_type == "access.permission.requested")
        .order_by(AuditLog.id.desc())
        .limit(1)
    ).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("permission_id") is not None
    assert md.get("channel") == "web"
    assert md.get("channel_user_id") == "owner1"


def test_outbound_gate_sensitive_audit_includes_channel(mem_db: Session) -> None:
    with bind_channel_origin({"channel": "telegram", "channel_user_id": "9"}):
        gate_outbound_http_body(
            "sk-" + "a" * 22,
            url="https://api.openai.com/v1/chat",
            method="POST",
            db=mem_db,
            owner_user_id="tg_9",
            instruction_source="chat",
        )
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    assert row.event_type == "access.sensitive_egress.warning"
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "telegram"
    assert md.get("channel_user_id") == "9"
