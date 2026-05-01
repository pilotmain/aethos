"""Coding agent adapter interface (Cursor, Aider, Codex, …)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.dev_runtime import NexaDevWorkspace


class CodingAgentAdapter(ABC):
    @abstractmethod
    def run(self, workspace: NexaDevWorkspace, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        ...


__all__ = ["CodingAgentAdapter"]
