"""Request-scoped web chat session id (so deep call chains can load the right ConversationContext)."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

_DEFAULT = "default"
_web_session_id: contextvars.ContextVar[str] = contextvars.ContextVar("web_session_id", default=_DEFAULT)


def get_web_session_id() -> str:
    return _web_session_id.get()


@contextmanager
def bind_web_session_id(session_id: str | None) -> Iterator[None]:
    s = (session_id or _DEFAULT).strip()[:64] or _DEFAULT
    tok = _web_session_id.set(s)
    try:
        yield
    finally:
        _web_session_id.reset(tok)
