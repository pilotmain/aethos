# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Idea intake, project workflow, and context resolution."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.conversation_context import ConversationContext
from app.models.project import Project
from app.services.conversation_context_service import (
    clear_pending_project,
    get_pending_project_dict,
    set_pending_project,
)
from app.services.idea_intake import (
    build_pending_project_payload,
    extract_idea_summary,
    is_create_project_confirmation,
    looks_like_new_idea,
    match_create_repo_request,
    slugify_project_key,
)
from app.services.idea_project_service import commit_pending_idea_as_project
from app.services.idea_workflow_routing import try_dev_scope_workflow, try_strategy_workflow
from app.services.project_registry import create_idea_project, get_default_project, get_project_by_key
from app.services.project_workflow import (
    DEFAULT_IDEA_WORKFLOW,
    format_project_workflow,
    resolve_project_key_for_workflow,
)


@pytest.fixture
def mem_db():
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, future=True)
    db = Sess()
    try:
        yield db
    finally:
        db.close()
        eng.dispose()


def test_looks_like_new_idea() -> None:
    assert looks_like_new_idea("I want to build a booking app for barbers") is True
    assert looks_like_new_idea("Why is the sky blue?") is False
    assert looks_like_new_idea("Random words") is False


def test_extract_idea_project_key() -> None:
    e = extract_idea_summary("I want to build a booking app for barbers")
    assert e["summary"]
    assert e["project_key"] and len(e["project_key"]) >= 3
    assert "booking" in e["project_key"] and "barber" in e["project_key"]
    assert e["project_name"]
    assert slugify_project_key("hello") == "hello"


def test_create_project_confirmation() -> None:
    assert is_create_project_confirmation("create project") is True
    assert is_create_project_confirmation("  Create project ") is True
    assert is_create_project_confirmation("not create") is False


def test_pending_in_context_roundtrip(mem_db) -> None:
    c = ConversationContext(
        user_id="u-idea",
        recent_messages_json="[]",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    pl = {
        "project_name": "Test",
        "project_key": "test",
        "summary": "I want to build a test",
        "recommended_workflow": ["strategy"],
    }
    set_pending_project(c, pl)
    mem_db.add(c)
    mem_db.commit()
    c2 = mem_db.get(ConversationContext, c.id)
    assert (get_pending_project_dict(c2) or {}).get("project_key") == "test"
    clear_pending_project(c2)
    mem_db.add(c2)
    mem_db.commit()
    assert get_pending_project_dict(c2) is None


def test_create_idea_project_and_workflow_list(mem_db) -> None:
    p = create_idea_project(
        mem_db,
        key="barber",
        display_name="Barber Booking",
        idea_summary="idea text",
    )
    assert p.repo_path is None
    assert p.idea_summary == "idea text"
    body = format_project_workflow(p)
    assert "Barber" in body
    assert len(DEFAULT_IDEA_WORKFLOW) == 5
    assert "Strategy" in body
    # workflow command
    from app.services.telegram_project_commands import format_project_workflow_cmd

    t = format_project_workflow_cmd(mem_db, "barber")
    assert "Workflow" in t


def test_strategy_validate_uses_context(mem_db) -> None:
    cctx = ConversationContext(
        user_id="u-2",
        recent_messages_json="[]",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    create_idea_project(
        mem_db, key="foo-idea", display_name="Foo", idea_summary="summary line"
    )
    mem_db.add(cctx)
    mem_db.commit()
    out = try_strategy_workflow("validate foo-idea", db=mem_db, cctx=cctx)
    assert "Strategy review" in (out or "")
    assert "summary line" in (out or "")


def test_dev_scope_no_repo_message(mem_db) -> None:
    cctx = ConversationContext(
        user_id="u-3",
        recent_messages_json="[]",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    p = create_idea_project(
        mem_db, key="nopath", display_name="No Path", idea_summary="x"
    )
    cctx.active_project = p.key
    mem_db.add(cctx)
    mem_db.commit()
    out = try_dev_scope_workflow("scope nopath", db=mem_db, cctx=cctx)
    assert out and "repo" in out.lower() and "create repo" in out


def test_match_create_repo() -> None:
    k = match_create_repo_request("create repo for my-app")
    assert k == "my-app"


def test_create_repo_approval_queued(mem_db) -> None:
    from app.models.user import User
    from app.services.agent_job_service import AgentJobService
    from app.services.idea_project_service import queue_create_repo_approval

    mem_db.add(
        User(
            id="u-9",
            is_new=True,
        )
    )
    mem_db.commit()
    create_idea_project(mem_db, key="crr", display_name="CRR", idea_summary="d")
    msg = queue_create_repo_approval(
        mem_db, "u-9", "crr", telegram_chat_id="1"
    )
    assert "create_repo" in msg
    assert "crr" in msg
    rows = AgentJobService().list_jobs(mem_db, "u-9", limit=1)
    assert rows and (rows[0].payload_json or {}).get("project_key") == "crr"
    assert (rows[0].command_type or "") == "create-idea-repo"


def test_resolve_active_it(mem_db) -> None:
    create_idea_project(mem_db, key="k1", display_name="A", idea_summary="")
    k, err = resolve_project_key_for_workflow(
        "it", db=mem_db, active_project_key="k1"
    )
    assert err is None and k == "k1"


def test_build_pending_payload() -> None:
    ex = extract_idea_summary("I have an idea: paint store")
    pl = build_pending_project_payload(ex)
    assert pl["project_key"] and "recommended_workflow" in pl


def test_commit_pending_creates_row(mem_db) -> None:
    c = ConversationContext(
        user_id="u-cm",
        recent_messages_json="[]",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    ex = extract_idea_summary("I want to build a test app for dogs")
    set_pending_project(c, build_pending_project_payload(ex))
    mem_db.add(c)
    mem_db.commit()
    msg = commit_pending_idea_as_project(mem_db, "u-cm", c)
    assert "Created project" in msg
    k = (get_pending_project_dict(c) or {}).get("project_key")
    assert k is None
    p = get_project_by_key(mem_db, ex["project_key"])
    assert p is not None
    assert p.display_name
