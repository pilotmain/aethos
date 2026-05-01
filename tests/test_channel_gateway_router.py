"""Channel Gateway Phase 3: router + core contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import (
    bind_channel_origin,
    get_channel_origin,
)
from app.services.web_chat_service import WebChatResult


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_passes_normalized_message_to_core(
    mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session
) -> None:
    norm = {
        "channel": "telegram",
        "channel_user_id": "123",
        "user_id": "tg_123",
        "message": "hello",
        "attachments": [],
        "metadata": {
            "channel_message_id": "456",
            "channel_chat_id": "789",
            "channel_thread_id": None,
            "username": "u",
            "display_name": "U",
        },
    }
    seen_origin: dict | None = None

    def _capture_origin(db, uid, text, **kw):
        nonlocal seen_origin
        seen_origin = dict(get_channel_origin() or {})
        return WebChatResult(reply="ok", intent="chat", agent_key="nexa")

    mock_core.side_effect = _capture_origin
    out = handle_incoming_channel_message(mem_db, normalized_message=norm)
    assert mock_core.called
    call = mock_core.call_args
    assert call.kwargs.get("web_session_id") == "default"
    assert call.args[1] == "tg_123"
    assert call.args[2] == "hello"
    assert seen_origin is not None
    assert seen_origin.get("channel") == "telegram"
    assert seen_origin.get("channel_user_id") == "123"
    assert seen_origin.get("channel_message_id") == "456"
    assert seen_origin.get("channel_thread_id") is None
    assert seen_origin.get("channel_chat_id") == "789"
    assert out["message"] == "ok"
    assert out["metadata"]["channel"] == "telegram"
    assert out["metadata"]["channel_user_id"] == "123"


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_permission_response_envelope(
    mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session
) -> None:
    pr = {"permission_request_id": "p1", "scope": "run", "target": "/tmp"}
    mock_core.return_value = WebChatResult(
        reply="need permission",
        intent="x",
        agent_key="nexa",
        permission_required=pr,
        response_kind="permission_required",
    )
    out = handle_incoming_channel_message(
        mem_db,
        normalized_message={
            "channel": "web",
            "channel_user_id": "web_u",
            "user_id": "web_u",
            "message": "run thing",
            "attachments": [],
            "metadata": {},
        },
    )
    assert out["permission_required"] == pr
    assert out["response_kind"] == "permission_required"


def test_router_module_does_not_import_executors() -> None:
    root = Path(__file__).resolve().parents[1]
    src = (root / "app/services/channel_gateway/router.py").read_text()
    assert "host_executor" not in src
    assert "AgentJobService" not in src


def test_build_channel_origin_for_web_session() -> None:
    n = {
        "channel": "web",
        "channel_user_id": "u1",
        "metadata": {"web_session_id": "sess-a", "channel_chat_id": None},
    }
    o = build_channel_origin(n)
    assert o["channel"] == "web"
    assert o["web_session_id"] == "sess-a"


def test_bind_channel_origin_context_var() -> None:
    assert get_channel_origin() is None
    with bind_channel_origin({"channel": "telegram", "channel_user_id": "1"}):
        assert get_channel_origin() is not None
        assert get_channel_origin().get("channel") == "telegram"
    assert get_channel_origin() is None
