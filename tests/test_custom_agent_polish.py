"""Polish: management commands, invalid paths, display handles, markdown cleanup."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.models.user_agent import UserAgent
from app.services.custom_agent_routing import try_deterministic_custom_agent_turn
from app.services.custom_agents import display_agent_handle, display_agent_handle_label
from app.services.local_file_intent import infer_local_file_request
from app.services.markdown_postprocess import clean_agent_markdown_output


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_clean_markdown_dangling_bold_numbered() -> None:
    raw = "1. Cost Reduction** — Primary ROI driver\n"
    out = clean_agent_markdown_output(raw)
    assert "**" not in out
    assert "Cost Reduction" in out


def test_display_agent_handle_hyphenates_underscore() -> None:
    assert display_agent_handle_label("research_analyst") == "research-analyst"
    assert display_agent_handle("research_analyst") == "@research-analyst"


def test_get_custom_agent_resolves_hyphen_to_stored_underscore(db_session) -> None:
    from app.services.custom_agents import get_custom_agent

    uid = f"pol_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="P", timezone="UTC", is_new=False))
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
    r = get_custom_agent(db_session, uid, "research-analyst")
    assert r is not None
    assert r.agent_key == "research_analyst"


def test_infer_explicit_missing_absolute_path_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request("read /bad/path/does_not_exist_12345.txt")
    assert lf.matched and lf.error_message
    assert "Path does not exist" in (lf.error_message or "")
    assert lf.clarification_message is None


def test_enable_command_ignores_trailing_task(db_session) -> None:
    uid = f"pol_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="P", timezone="UTC", is_new=False))
    db_session.add(
        UserAgent(
            owner_user_id=uid,
            agent_key="research_analyst",
            display_name="RA",
            description="",
            system_prompt="You are helpful.",
            is_active=False,
        )
    )
    db_session.commit()
    msg = try_deterministic_custom_agent_turn(
        db_session,
        uid,
        "enable @research-analyst read /Users/nope/README.md and summarize it",
    )
    assert msg is not None
    assert "Enabled" in msg
    assert "Please resend" in msg

    row = db_session.scalars(select(UserAgent).where(UserAgent.owner_user_id == uid)).one()
    assert row.is_active is True

