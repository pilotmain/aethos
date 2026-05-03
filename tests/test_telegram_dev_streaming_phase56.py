"""Phase 56 — Telegram progress hook schedules replies on the bot loop."""

from __future__ import annotations

import asyncio

import pytest

from app.services.telegram_dev_progress import make_telegram_dev_progress_hook


def test_make_telegram_dev_progress_hook_schedules_on_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduled: list[tuple] = []

    def _capture(coro, loop):
        scheduled.append((coro, loop))
        if asyncio.iscoroutine(coro):
            coro.close()

        class _Fut:
            def result(self, timeout=None):
                return None

        return _Fut()

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _capture)

    class _Msg:
        def reply_text(self, text: str):
            async def _coro():
                return text

            return _coro()

    class _Up:
        message = _Msg()

    loop = asyncio.new_event_loop()
    try:
        hook = make_telegram_dev_progress_hook(_Up(), loop=loop, prefix="→ ")
        hook("Running tests")
    finally:
        loop.close()

    assert len(scheduled) == 1
    _coro, loop_used = scheduled[0]
    assert loop_used is loop
    assert asyncio.iscoroutine(_coro)
