# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Context for LLM usage metadata (per asyncio task / thread). No prompts or secrets.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from typing import Any, Iterator

from app.services.llm_request_context import get_llm_telegram_context


@dataclass
class LlmUsageState:
    source: str = "unknown"
    agent_key: str | None = "aethos"
    action_type: str = "chat_response"
    user_id: str | None = None
    telegram_user_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    # Optional: DB for recording when llm_telegram_context has no session (e.g. web w/o tg)
    db: Any | None = field(default=None, repr=False, compare=False)

    def to_field_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "db":
                continue
            d[f.name] = getattr(self, f.name)
        return d


_cv: contextvars.ContextVar[LlmUsageState] = contextvars.ContextVar(
    "llm_usage_state",
    default=LlmUsageState(),
)


def get_llm_usage_context() -> LlmUsageState:
    return _cv.get()


@contextmanager
def bind_llm_usage_context(
    *,
    source: str | None = None,
    agent_key: str | None = None,
    action_type: str | None = None,
    user_id: str | None = None,
    telegram_user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    db: Any | None = None,
) -> Iterator[None]:
    old = get_llm_usage_context()
    o = old.to_field_dict()
    o["db"] = old.db
    if source is not None:
        o["source"] = source
    if agent_key is not None:
        o["agent_key"] = agent_key
    if action_type is not None:
        o["action_type"] = action_type
    if user_id is not None:
        o["user_id"] = user_id
    if telegram_user_id is not None:
        o["telegram_user_id"] = telegram_user_id
    if session_id is not None:
        o["session_id"] = session_id
    if request_id is not None:
        o["request_id"] = request_id
    if db is not None:
        o["db"] = db
    st = LlmUsageState(**o)
    t = _cv.set(st)
    try:
        yield
    finally:
        _cv.reset(t)


@contextmanager
def push_llm_action(
    *,
    action_type: str | None = None,
    agent_key: str | None = None,
    source: str | None = None,
) -> Iterator[None]:
    with bind_llm_usage_context(
        action_type=action_type,
        agent_key=agent_key,
        source=source,
    ):
        yield


def reset_llm_usage_state() -> None:
    _cv.set(LlmUsageState())


def bind_llm_usage_telegram(
    db: Any,
    app_user_id: str,
    telegram_user_id: int,
) -> object:
    """Set usage defaults for a Telegram-originated turn (no prompts; for metadata only)."""
    from uuid import uuid4

    st = LlmUsageState(
        source="telegram",
        user_id=app_user_id,
        telegram_user_id=str(int(telegram_user_id)),
        session_id="default",
        action_type="chat_response",
        agent_key="aethos",
        db=db,
        request_id=str(uuid4()),
    )
    return _cv.set(st)


def unbind_llm_usage(token: object) -> None:
    _cv.reset(token)  # type: ignore[arg-type]


def resolve_db_for_usage() -> Any | None:
    s = get_llm_usage_context()
    if s.db is not None:
        return s.db
    db, _t = get_llm_telegram_context()
    return db
