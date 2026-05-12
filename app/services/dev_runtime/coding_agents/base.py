# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Coding agent adapter interface — Phase 24."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CodingAgentRequest:
    user_id: str
    run_id: str
    workspace_id: str
    repo_path: str
    goal: str
    context: dict[str, Any]
    max_iterations: int = 3
    allow_write: bool = False
    allow_commit: bool = False
    allow_push: bool = False
    cost_budget_usd: float = 0.0


@dataclass
class CodingAgentResult:
    ok: bool
    provider: str
    summary: str
    changed_files: list[str]
    commands_run: list[str]
    test_result: dict[str, Any] | None = None
    error: str | None = None


class CodingAgentAdapter(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def run(self, request: CodingAgentRequest) -> CodingAgentResult:
        raise NotImplementedError


__all__ = [
    "CodingAgentAdapter",
    "CodingAgentRequest",
    "CodingAgentResult",
]
