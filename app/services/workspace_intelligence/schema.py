# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Structured workspace context pack (file-backed, lightweight)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkspaceContextPack:
    """Selected workspace files + skill hints for one turn."""

    files: list[str] = field(default_factory=list)
    file_contents: dict[str, str] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    summary: str = ""
    token_estimate: int = 0


__all__ = ["WorkspaceContextPack"]
