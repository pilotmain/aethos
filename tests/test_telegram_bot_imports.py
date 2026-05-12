# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Regression: telegram bot must import without channel_gateway / audit cycles."""


def test_telegram_bot_module_imports() -> None:
    import app.bot.telegram_bot  # noqa: F401


def test_channel_origin_public_api() -> None:
    from app.services.channel_gateway.origin_context import (
        bind_channel_origin,
        get_channel_origin,
    )

    with bind_channel_origin({"channel": "telegram", "channel_user_id": "1"}):
        o = get_channel_origin()
        assert o is not None
        assert o.get("channel") == "telegram"
    assert get_channel_origin() is None
