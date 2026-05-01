import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

from telegram import Update
from telegram.constants import ChatAction


@asynccontextmanager
async def typing_indicator(
    update: Update,
    context: Any = None,
    interval_seconds: float = 3.0,
    min_visible_seconds: float = 0.8,
):
    """
    Keeps Telegram "typing…" visible while processing.

    Telegram often expires the typing state after a few seconds, so we resend in a loop.
    Optional minimum visible time helps short replies still show the indicator.
    """
    chat = update.effective_chat

    if not chat:
        yield
        return

    stop_event = asyncio.Event()
    started_at = time.perf_counter()

    async def _send_typing() -> None:
        if hasattr(chat, "send_action"):
            try:
                await chat.send_action(ChatAction.TYPING)  # type: ignore[union-attr]
                return
            except Exception:  # noqa: BLE001 — best-effort UX; never break the handler
                pass
        if context is not None:
            bot = getattr(context, "bot", None)
            if bot is not None and getattr(chat, "id", None) is not None:
                try:
                    await bot.send_chat_action(  # type: ignore[union-attr]
                        chat_id=chat.id,
                        action=ChatAction.TYPING,
                    )
                except Exception:  # noqa: BLE001
                    pass

    async def _runner() -> None:
        while not stop_event.is_set():
            await _send_typing()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:  # noqa: S110 — loop until stopped
                continue

    task = asyncio.create_task(_runner())

    try:
        yield
    finally:
        elapsed = time.perf_counter() - started_at
        remaining = min_visible_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:  # noqa: S110
            pass
        except Exception:  # noqa: BLE001
            pass
