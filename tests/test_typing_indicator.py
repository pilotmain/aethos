import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.constants import ChatAction

from app.bot.typing import typing_indicator


def _run(coro: object) -> None:
    asyncio.run(coro)  # type: ignore[arg-type]


def test_typing_indicator_sends_typing() -> None:
    bot = AsyncMock()
    chat = SimpleNamespace(id=99)
    update = SimpleNamespace(
        effective_chat=chat, effective_message=object()
    )
    context = SimpleNamespace(bot=bot)

    async def _() -> None:
        async with typing_indicator(
            update, context, interval_seconds=0.2, min_visible_seconds=0
        ):
            await asyncio.sleep(0.05)

    _run(_())

    assert bot.send_chat_action.await_count >= 1
    assert bot.send_chat_action.call_args.kwargs.get("action") is ChatAction.TYPING
    assert bot.send_chat_action.call_args.kwargs.get("chat_id") == 99


def test_typing_indicator_noop_without_bot() -> None:
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=1))

    async def _() -> None:
        async with typing_indicator(update, None, interval_seconds=0.1, min_visible_seconds=0):
            pass

    _run(_())


def test_typing_ignores_send_action_failures() -> None:
    calls = 0

    async def flappy(**_a: object) -> None:  # noqa: ARG001
        nonlocal calls
        calls += 1
        if calls < 4:
            raise OSError("network down")

    bot = SimpleNamespace(send_chat_action=AsyncMock(side_effect=flappy))
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=7),
        effective_message=object(),
    )
    context = SimpleNamespace(bot=bot)

    async def _() -> None:
        async with typing_indicator(
            update, context, interval_seconds=0.02, min_visible_seconds=0
        ):
            await asyncio.sleep(0.1)

    _run(_())
    assert calls >= 4


def test_typing_helper_min_visible_does_not_crash() -> None:
    """Short body + min_visible pads total time; must complete without error."""
    bot = AsyncMock()
    chat = SimpleNamespace(id=3, send_action=AsyncMock())
    update = SimpleNamespace(
        effective_chat=chat,
        effective_message=object(),
    )
    context = SimpleNamespace(bot=bot)

    async def _() -> None:
        async with typing_indicator(
            update, context, interval_seconds=0.2, min_visible_seconds=0.05
        ):
            pass

    _run(_())
    assert chat.send_action.await_count >= 1
