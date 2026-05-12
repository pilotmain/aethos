# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

_channel_origin: ContextVar[dict[str, Any] | None] = ContextVar(
    "channel_origin", default=None
)


def get_channel_origin() -> dict[str, Any] | None:
    """Channel metadata for the active inbound request (set by router or Telegram bind)."""
    return _channel_origin.get()


@contextmanager
def bind_channel_origin(
    meta: dict[str, Any] | None,
) -> Generator[None, None, None]:
    token = _channel_origin.set(meta)
    try:
        yield
    finally:
        _channel_origin.reset(token)
