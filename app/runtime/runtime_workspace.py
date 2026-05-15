# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ensure ``~/.aethos/workspace`` and ``~/.aethos/logs`` exist."""

from __future__ import annotations

from app.core.paths import get_aethos_home_dir, get_aethos_workspace_root


def ensure_runtime_workspace_layout() -> None:
    get_aethos_home_dir().mkdir(parents=True, exist_ok=True)
    (get_aethos_home_dir() / "logs").mkdir(parents=True, exist_ok=True)
    get_aethos_workspace_root().mkdir(parents=True, exist_ok=True)
