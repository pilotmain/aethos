"""End-to-end custom agent primitive: routing, parse, create, no host misroute."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.audit_log import AuditLog  # noqa: F401 — register table
from app.models.user import User
from app.models.user_agent import UserAgent
from app.services.custom_agent_parser import parse_custom_agent_from_prompt
from app.services.custom_agent_routing import (
    custom_agent_message_blocks_folder_heuristics,
    is_create_custom_agent_request,
    try_deterministic_custom_agent_turn,
)
from app.services.custom_agents import (
    create_custom_agent_from_prompt,
    format_custom_agent_describe_reply,
    get_custom_agent,
)

MULTI_AGENT_QUESTION = (
    "can you create multi agents that can communicate each other autonomously "
    "and do some task without my involvement?"
)
from app.services.local_file_intent import infer_local_file_request


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        uid = f"u_{uuid.uuid4().hex[:12]}"
        db.add(User(id=uid, email=None))
        db.commit()
        yield db
    finally:
        db.close()
        engine.dispose()


LEGAL_PROMPT = (
    "Create me a custom agent called @legal-reviewer. It should review contracts, summarize risks, "
    "draft questions, and require human review before final decisions."
)


def test_create_legal_reviewer_parse_and_db(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    spec = parse_custom_agent_from_prompt(LEGAL_PROMPT)
    assert spec is not None
    assert spec.handle == "legal-reviewer"
    assert spec.safety_level == "regulated"
    assert any("human" in (g or "").lower() or "review" in (g or "").lower() for g in spec.guardrails)

    body = create_custom_agent_from_prompt(mem_db, user_id=str(uid), prompt=LEGAL_PROMPT)
    assert "Created custom agent @legal-reviewer" in body or "legal-reviewer" in body
    assert "Analyze folder" not in body
    assert "read_multiple_files" not in body.lower()
    row = get_custom_agent(mem_db, str(uid), "legal_reviewer")
    assert row is not None
    assert row.safety_level == "regulated"


def test_no_folder_heuristic_misroute() -> None:
    assert custom_agent_message_blocks_folder_heuristics(LEGAL_PROMPT) is True
    lf = infer_local_file_request(LEGAL_PROMPT)
    assert lf.matched is False


def test_builtin_collision_dev(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    body = create_custom_agent_from_prompt(
        mem_db,
        user_id=str(uid),
        prompt="Create me a custom agent called @dev for coding help.",
    )
    assert "reserved" in body.lower()
    assert get_custom_agent(mem_db, str(uid), "dev") is None


def test_list_after_create(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    create_custom_agent_from_prompt(mem_db, user_id=str(uid), prompt=LEGAL_PROMPT)
    out = try_deterministic_custom_agent_turn(mem_db, str(uid), "list my agents")
    assert out is not None
    assert "legal" in out.lower() or "legal_reviewer" in out.lower()


def test_regulated_misuse_blocks_creation(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    body = create_custom_agent_from_prompt(
        mem_db,
        user_id=str(uid),
        prompt="Create @lawyer to give final legal advice and replace my attorney",
    )
    assert "replace" in body.lower() or "can’t" in body.lower() or "can't" in body.lower() or "cannot" in body.lower()
    assert get_custom_agent(mem_db, str(uid), "lawyer") is None


def test_is_create_request_deprecated() -> None:
    assert not is_create_custom_agent_request(
        "Create me a custom agent called @task-bot for tasks."
    )
    assert not is_create_custom_agent_request("What is the weather?")
    assert not is_create_custom_agent_request(MULTI_AGENT_QUESTION)


def test_multi_agent_question_does_not_create_user_agent(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    body = create_custom_agent_from_prompt(mem_db, user_id=str(uid), prompt=MULTI_AGENT_QUESTION)
    assert "Created custom agent" not in body
    rows = mem_db.query(UserAgent).filter(UserAgent.owner_user_id == str(uid)).all()
    assert len(rows) == 0


def test_deterministic_turn_no_longer_creates_llm_custom_agent(mem_db: Session) -> None:
    """Phase 48: NL creation uses orchestration registry (see try_spawn_natural_sub_agents)."""
    uid = mem_db.query(User).first().id
    out = try_deterministic_custom_agent_turn(mem_db, str(uid), LEGAL_PROMPT)
    assert out is None


def test_describe_custom_agent(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    create_custom_agent_from_prompt(mem_db, user_id=str(uid), prompt=LEGAL_PROMPT)
    out = format_custom_agent_describe_reply(mem_db, str(uid), "legal-reviewer")
    assert "legal" in out.lower() or "legal_reviewer" in out.lower()
    assert "Safety" in out or "safety" in out.lower()


def test_disabled_agent_not_callable(mem_db: Session) -> None:
    uid = mem_db.query(User).first().id
    create_custom_agent_from_prompt(mem_db, user_id=str(uid), prompt=LEGAL_PROMPT)
    row = get_custom_agent(mem_db, str(uid), "legal_reviewer")
    assert row is not None
    row.is_active = False
    mem_db.add(row)
    mem_db.commit()
    out = try_deterministic_custom_agent_turn(
        mem_db,
        str(uid),
        "enable @legal-reviewer",
    )
    assert out is not None
    assert "Enabled" in out
    mem_db.refresh(row)
    assert row.is_active is True
