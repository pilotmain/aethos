# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace directory persistence under ``~/.aethos``."""

from __future__ import annotations

from app.core.paths import get_aethos_workspace_root
from app.runtime.runtime_workspace import ensure_runtime_workspace_layout


def test_workspace_dir_is_created(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    ensure_runtime_workspace_layout()
    assert get_aethos_workspace_root().is_dir()
