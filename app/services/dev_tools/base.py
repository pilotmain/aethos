# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DevToolResult:
    ok: bool
    message: str
    details: str | None = None


class DevToolConnector(ABC):
    key: str
    display_name: str
    supported_modes: list[str]

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        pass

    def run_autonomous(self, repo_path: Path, task_file: Path) -> DevToolResult:
        return DevToolResult(
            ok=False,
            message=f"{self.display_name} does not support autonomous execution.",
        )
