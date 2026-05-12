# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Telegram — stream dev-mission progress lines without moving DB work off-thread."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from telegram import Update


def make_telegram_dev_progress_hook(
    update: Update,
    *,
    loop: asyncio.AbstractEventLoop,
    prefix: str = "→ ",
) -> Callable[[str], None]:
    """
    Return a sync callback safe to pass as ``on_progress`` into :func:`~app.services.dev_runtime.service.run_dev_mission`.

    Schedules ``reply_text`` on the bot event loop from the thread running the dev mission
    (same thread as structured gateway + DB session).
    """

    def _hook(msg: str) -> None:
        text = f"{prefix}{(msg or '').strip()}".strip()
        if not text:
            return
        coro = update.message.reply_text(text[:4000])
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            pass

    return _hook


__all__ = ["make_telegram_dev_progress_hook"]
