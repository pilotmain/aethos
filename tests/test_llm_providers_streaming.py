# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Streaming completions (Phase 11.5)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm.base import Message
from app.services.llm.providers.openai_backend import OpenAIBackend


def test_openai_streaming_yields_text():
    async def _run() -> None:
        provider = OpenAIBackend(logical_name="openai", api_key="test", model="gpt-4o-mini")
        messages = [Message(role="user", content="Hello")]

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        mock_chunk.choices[0].delta.content = "Hello"

        async def fake_create(**kwargs: object) -> object:
            async def _chunks():
                yield mock_chunk

            return _chunks()

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)

        out: list[str] = []
        with patch(
            "app.services.llm.providers.openai_backend.build_async_openai_client",
            return_value=mock_client,
        ):
            async for chunk in provider.complete_chat_streaming(messages):
                out.append(chunk)

        assert out == ["Hello"]
        mock_client.chat.completions.create.assert_called_once()

    asyncio.run(_run())
