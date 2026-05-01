"""LLM key resolution for custom agents (user BYOK + system env)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import Base
from app.models.user import User
from app.services.custom_agents import can_user_create_custom_agents
from app.services.llm_key_resolution import resolve_llm_for_user


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
        yield db
    finally:
        db.close()
        engine.dispose()


def test_resolve_system_key_no_byok(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "use_real_llm", True, raising=False)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-api03-testkeyfortests", raising=False)
    monkeypatch.setattr(s, "openai_api_key", None, raising=False)
    uid = f"web_{uuid.uuid4().hex[:10]}"
    mem_db.add(User(id=uid, email=None))
    mem_db.commit()
    r = resolve_llm_for_user(mem_db, uid)
    assert r.available is True
    assert r.source == "system"
    assert r.provider == "anthropic"


def test_resolve_none_when_no_keys(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "use_real_llm", True, raising=False)
    monkeypatch.setattr(s, "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(s, "openai_api_key", None, raising=False)
    uid = f"web_{uuid.uuid4().hex[:10]}"
    mem_db.add(User(id=uid, email=None))
    mem_db.commit()
    r = resolve_llm_for_user(mem_db, uid)
    assert r.available is False
    assert r.source == "none"
    assert r.reason


def test_guest_can_create_with_system_key_only(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "use_real_llm", True, raising=False)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-api03-testkeyfortests", raising=False)
    monkeypatch.setattr(s, "openai_api_key", None, raising=False)
    uid = f"web_{uuid.uuid4().hex[:10]}"
    mem_db.add(User(id=uid, email=None))
    mem_db.commit()
    ok, err = can_user_create_custom_agents(mem_db, uid)
    assert ok is True
    assert err is None


def test_guest_blocked_when_no_keys_and_use_real_llm(
    mem_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "use_real_llm", True, raising=False)
    monkeypatch.setattr(s, "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(s, "openai_api_key", None, raising=False)
    uid = f"web_{uuid.uuid4().hex[:10]}"
    mem_db.add(User(id=uid, email=None))
    mem_db.commit()
    ok, err = can_user_create_custom_agents(mem_db, uid)
    assert ok is False
    assert err
    assert "ANTHROPIC" in err or "OPENAI" in err or "LLM" in err


def test_use_real_llm_off_unavailable(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "use_real_llm", False, raising=False)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-x", raising=False)
    r = resolve_llm_for_user(mem_db, "web_x")
    assert r.available is False
    assert "USE_REAL_LLM" in (r.reason or "")
