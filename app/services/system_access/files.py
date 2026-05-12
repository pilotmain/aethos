# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded file reads for agent tools."""

from __future__ import annotations

from pathlib import Path

from app.services.system_access.permissions import assert_workspace_path


def read_text_file(
    path: str | Path,
    *,
    roots: list[str],
    max_bytes: int = 262_144,
) -> str:
    p = assert_workspace_path(path, roots=roots)
    raw = p.read_bytes()[:max_bytes]
    return raw.decode("utf-8", errors="replace")


__all__ = ["read_text_file"]
