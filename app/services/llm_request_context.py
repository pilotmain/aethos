# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Per-request context for Telegram-originated LLM calls: optional DB + telegram user id.
Set by the Telegram message handler; read by :mod:`app.services.llm_key_resolution` and
:func:`app.services.user_api_keys` to merge user keys with system env keys.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any

_db_cv: contextvars.ContextVar[Any | None] = contextvars.ContextVar("llm_ctx_db", default=None)
_tid_cv: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "llm_ctx_telegram_id", default=None
)


@contextmanager
def llm_telegram_context(db, telegram_user_id: int | None):
    """Bind DB and Telegram user for merged LLM key resolution in this call stack (asyncio-safe)."""
    t0 = _db_cv.set(db)
    t1 = _tid_cv.set(telegram_user_id)
    try:
        yield
    finally:
        _db_cv.reset(t0)
        _tid_cv.reset(t1)


def get_llm_telegram_context() -> tuple[Any | None, int | None]:
    return _db_cv.get(), _tid_cv.get()


def bind_llm_telegram(db, telegram_id: int) -> tuple[object, object]:
    d = _db_cv.set(db)
    t = _tid_cv.set(telegram_id)
    return (d, t)


def unbind_llm_telegram(tokens: tuple[object, object]) -> None:
    d, t = tokens
    _tid_cv.reset(t)
    _db_cv.reset(d)
