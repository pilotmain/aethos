# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Channel Gateway Phase 2: ChannelUser mapping and normalized metadata."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.channel_user import ChannelUser
from app.models.telegram_link import TelegramLink
from app.services.channel_gateway.identity import resolve_channel_user
from app.services.channel_gateway.metadata import channel_audit_metadata
from app.services.channel_gateway.telegram_adapter import TelegramAdapter


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine, tables=[ChannelUser.__table__, TelegramLink.__table__])
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_channel_user_create_telegram(mem_db: Session) -> None:
    uid = resolve_channel_user(
        mem_db,
        channel="telegram",
        channel_user_id="123",
        default_user_id="tg_123",
        display_name="Alice",
        username="alice",
    )
    assert uid == "tg_123"
    row = mem_db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == "telegram",
            ChannelUser.channel_user_id == "123",
        )
    )
    assert row is not None
    assert row.user_id == "tg_123"
    assert row.display_name == "Alice"
    assert row.username == "alice"


def test_channel_user_reuse_same_user_id_no_duplicate_row(mem_db: Session) -> None:
    r1 = resolve_channel_user(
        mem_db,
        channel="telegram",
        channel_user_id="123",
        default_user_id="tg_123",
    )
    r2 = resolve_channel_user(
        mem_db,
        channel="telegram",
        channel_user_id="123",
        default_user_id="tg_123",
    )
    assert r1 == r2 == "tg_123"
    n = mem_db.scalar(select(func.count()).select_from(ChannelUser))
    assert int(n or 0) == 1


def test_cross_channel_same_channel_user_id_string_no_collision(mem_db: Session) -> None:
    resolve_channel_user(
        mem_db,
        channel="telegram",
        channel_user_id="123",
        default_user_id="tg_123",
    )
    resolve_channel_user(
        mem_db,
        channel="slack",
        channel_user_id="123",
        default_user_id="slack_workspace_member_123",
    )
    rows = mem_db.scalars(select(ChannelUser).order_by(ChannelUser.channel)).all()
    assert len(rows) == 2
    by_ch = {r.channel: r.user_id for r in rows}
    assert by_ch["telegram"] == "tg_123"
    assert by_ch["slack"] == "slack_workspace_member_123"


def test_telegram_adapter_resolve_backward_compatible_tg_prefix(mem_db: Session) -> None:
    adapter = TelegramAdapter()
    upd = SimpleNamespace(
        update_id=42,
        effective_user=SimpleNamespace(id=123, username="bob", first_name="Bob", last_name="B"),
        effective_chat=SimpleNamespace(id=999001),
        message=SimpleNamespace(text="hello", message_id=7, message_thread_id=None),
    )
    assert adapter.resolve_app_user_id(mem_db, upd) == "tg_123"


def test_normalize_message_includes_channel_metadata() -> None:
    adapter = TelegramAdapter()
    upd = SimpleNamespace(
        update_id=99,
        effective_user=SimpleNamespace(
            id=123,
            username="bob",
            first_name="Bob",
            last_name="Builder",
        ),
        effective_chat=SimpleNamespace(id=555),
        message=SimpleNamespace(text="hello", message_id=7, message_thread_id=None),
    )
    n = adapter.normalize_message(upd, app_user_id="tg_123")
    assert n["channel"] == "telegram"
    assert n["channel_user_id"] == "123"
    assert n["user_id"] == "tg_123"
    assert n["app_user_id"] == "tg_123"
    assert n["message"] == "hello"
    assert n["text"] == "hello"
    assert n["attachments"] == []
    assert n["metadata"]["channel_message_id"] == "7"
    assert n["metadata"]["channel_chat_id"] == "555"
    assert n["metadata"]["channel_thread_id"] is None
    assert n["metadata"]["username"] == "bob"
    assert n["metadata"]["display_name"] == "Bob Builder"
    assert n["metadata"]["update_id"] == 99


def test_channel_audit_metadata_helper() -> None:
    norm = {
        "channel": "telegram",
        "channel_user_id": "123",
        "metadata": {
            "channel_message_id": "7",
            "channel_thread_id": None,
        },
    }
    assert channel_audit_metadata(norm) == {
        "channel": "telegram",
        "channel_user_id": "123",
        "channel_message_id": "7",
        "channel_thread_id": None,
    }
