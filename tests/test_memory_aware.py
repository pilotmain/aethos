# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.audit_log import AuditLog
from app.models.learning_event import LearningEvent
from app.models.project import Project
from app.services import system_memory_files as smf
from app.services.agent_router import route_agent
from app.services.learning_event_service import approve as learning_approve
from app.services.memory_aware_routing import apply_memory_aware_route_adjustment
from app.services.memory_preferences import (
    extract_memory_preferences,
    get_memory_preferences_dict,
    maybe_apply_single_plain_cursor_block,
    user_requests_cursor_instructions,
)
from app.services.telegram_memory_commands import (
    format_memory_status,
    handle_memory_command,
    handle_memory_search,
)


@pytest.fixture
def mem_root(tmp_path, monkeypatch):
    monkeypatch.setattr(smf, "project_root", lambda: tmp_path)
    return tmp_path


def test_extract_cursor_plain_block_preference() -> None:
    mem = "User prefers Cursor instructions as one strict plain text block."
    p = extract_memory_preferences(mem, "")
    assert p["preferred_cursor_format"] == "single_plain_text_block"


def test_maybe_apply_cursor_plain_strips_fence(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.memory_preferences.get_memory_preferences_dict",
        lambda: {"preferred_cursor_format": "single_plain_text_block"},
    )
    out = maybe_apply_single_plain_cursor_block(
        "```\nline1\nline2\n```",
        "Give me cursor instructions for the fix",
    )
    assert "```" not in out
    assert "line1" in out


def test_user_requests_cursor_instructions() -> None:
    assert user_requests_cursor_instructions("paste for cursor")
    assert not user_requests_cursor_instructions("hello")


def test_memory_status_and_search(mem_root) -> None:
    smf.ensure_system_memory_files()
    (mem_root / "memory.md").write_text(
        (mem_root / "memory.md").read_text(encoding="utf-8")
        + "\n### 2099-01-01T00:00:00Z — test\n\nhello cursor world\n",
        encoding="utf-8",
    )
    st = format_memory_status()
    assert "Nexa memory status" in st
    assert "soul.md:" in st
    assert "durable preferences detected" in st
    sr = handle_memory_search("/memory search cursor")
    assert "cursor" in sr.lower()


def test_handle_memory_command_status(mem_root) -> None:
    smf.ensure_system_memory_files()
    body = handle_memory_command("/memory status")
    assert "memory.md" in body


def test_ambiguous_what_next_uses_active_project() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(bind=engine, tables=[Project.__table__])
    db = Session()
    db.add(
        Project(
            key="nexa",
            display_name="Nexa",
            provider_key="local",
            is_default=True,
            is_enabled=True,
        )
    )
    db.commit()

    r0 = route_agent("what next?", context_snapshot={})
    assert r0["agent_key"] == "aethos"
    r = apply_memory_aware_route_adjustment(
        r0,
        "what next?",
        {"active_project": "nexa"},
        db,
    )
    assert r["agent_key"] == "developer"
    assert r.get("resolved_project_key") == "nexa"
    db.close()
    engine.dispose()


def test_approved_learning_appends_to_memory_md(mem_root) -> None:
    smf.ensure_system_memory_files()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(
        bind=engine, tables=[LearningEvent.__table__, AuditLog.__table__]
    )
    db = Session()
    ev = LearningEvent(
        user_id="u1",
        agent_key="nexa",
        observation="User likes short answers",
        proposed_rule="Prefer concise replies",
        status="pending",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    class _Mem:
        def remember_note(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            return None

    learning_approve(
        db,
        "u1",
        ev.id,
        apply_to_memory=True,
        memory_service=_Mem(),
    )
    mem_txt = (mem_root / "memory.md").read_text(encoding="utf-8")
    assert "concise" in mem_txt.lower() or "learning" in mem_txt.lower()
    db.close()
    engine.dispose()


def test_append_still_rejects_secrets(mem_root) -> None:
    smf.ensure_system_memory_files()
    out = handle_memory_command("/memory add sk-live-deadbeef")
    assert "won’t store" in out.lower() or "secret" in out.lower()


def test_get_memory_preferences_reads_files(mem_root, monkeypatch) -> None:
    smf.ensure_system_memory_files()
    (mem_root / "memory.md").write_text(
        (mem_root / "memory.md").read_text(encoding="utf-8")
        + "\nUser wants one strict plain text block for Cursor.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.safe_llm_gateway.read_safe_system_memory_snapshot",
        smf.read_system_memory_snapshot,
    )
    p = get_memory_preferences_dict()
    assert p.get("preferred_cursor_format") == "single_plain_text_block"
