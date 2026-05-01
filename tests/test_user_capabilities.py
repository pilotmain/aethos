"""User capability modes, env lists, and access gating (no real secrets)."""

from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.telegram_link import TelegramLink
from app.models.audit_log import AuditLog
from app.services.user_capabilities import (
    AccessContext,
    access_section_for_doctor,
    can_write_global_memory_file,
    get_bootstrap_telegram_user_id,
    get_telegram_role,
    make_access,
    parse_telegram_id_list,
)
from app.services.telegram_access_audit import log_access_denied


def test_parse_telegram_id_list_strips():
    s = parse_telegram_id_list(" 1, 2, 3 ")
    assert s == {1, 2, 3}
    assert parse_telegram_id_list("") == set()


@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    from sqlalchemy.orm import Session as SASession

    Base.metadata.create_all(
        bind=engine, tables=[TelegramLink.__table__, AuditLog.__table__]
    )
    S = sessionmaker(bind=engine, class_=SASession, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _link(db, tid: int):
    t = TelegramLink(
        telegram_user_id=tid,
        app_user_id=f"tg_{tid}",
        chat_id=1,
        username="u",
    )
    db.add(t)
    db.commit()
    return t


def test_bootstrap_first_user_is_owner(mem_db, monkeypatch):
    monkeypatch.delenv("TELEGRAM_OWNER_IDS", raising=False)
    monkeypatch.delenv("TELEGRAM_TRUSTED_USER_IDS", raising=False)
    _link(mem_db, 100)
    assert get_bootstrap_telegram_user_id(mem_db) == 100
    assert get_telegram_role(100, mem_db) == "owner"
    _link(mem_db, 200)
    assert get_telegram_role(200, mem_db) == "guest"


def test_explicit_owner_list(mem_db, monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_IDS", "300")
    monkeypatch.setenv("TELEGRAM_TRUSTED_USER_IDS", "400")
    _link(mem_db, 300)
    _link(mem_db, 400)
    _link(mem_db, 500)
    assert get_telegram_role(300, mem_db) == "owner"
    assert get_telegram_role(400, mem_db) == "trusted"
    assert get_telegram_role(500, mem_db) == "guest"


def test_guest_cannot_write_global_memory():
    assert can_write_global_memory_file("guest") is False
    assert can_write_global_memory_file("owner") is True


def test_access_cli_and_ac_context(mem_db, monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_IDS", "9")
    _link(mem_db, 9)
    a = make_access(mem_db, 9, "tg_9", "a")
    assert isinstance(a, AccessContext)
    assert a.role == "owner"


def test_log_access_no_secrets_in_audit(mem_db, monkeypatch):
    log_access_denied(
        mem_db,
        app_user_id="tg_1",
        telegram_id=1,
        username="x",
        command_family="m",
        reason="r",
        preview="ok",
    )
    from sqlalchemy import text

    r = mem_db.execute(text("SELECT message, metadata_json FROM audit_logs"))
    row = r.mappings().fetchone()
    assert row
    assert "sk-proj" not in (row["message"] or "")
    raw_meta = row["metadata_json"] or {}
    if isinstance(raw_meta, str):
        raw_meta = json.loads(raw_meta)
    assert (raw_meta or {}).get("allowed") is False


def test_access_section_doctor_contains_runtime_words(mem_db, monkeypatch):
    monkeypatch.delenv("TELEGRAM_OWNER_IDS", raising=False)
    _link(mem_db, 99)
    s = access_section_for_doctor(99, mem_db)
    assert "Access" in s
    assert "TELEGRAM_OWNER" in s or "role" in s
