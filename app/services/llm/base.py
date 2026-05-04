"""
Abstract LLM provider interface (Phase 11) — implementations live under ``providers/``.

Vendor SDK construction uses :mod:`app.services.providers.sdk` only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    """Normalized chat message."""

    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class Tool:
    """OpenAI-style tool definition."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ModelInfo:
    id: str
    name: str
    provider: str
    context_length: int
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool


class LLMProvider(ABC):
    """Abstract chat completion provider."""

    logical_name: str = ""

    @abstractmethod
    def complete_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format_json: bool = False,
        tools: list[Tool] | None = None,
    ) -> str:
        """Non-streaming completion; returns assistant text (or JSON text when ``response_format_json``)."""

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Describe the configured model."""

    def validate_api_key(self) -> bool:
        return True


__all__ = ["LLMProvider", "Message", "ModelInfo", "Tool"]
