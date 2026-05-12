# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 23 — workspace registration + path validation."""

from __future__ import annotations

import subprocess

import pytest

from app.core.config import get_settings
from app.services.dev_runtime.workspace import (
    register_workspace,
    validate_workspace_path,
)


def test_register_workspace_tmp_git_repo(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    get_settings.cache_clear()
    try:
        row = register_workspace(db_session, "web_ws_u1", "t", str(repo))
        assert row.id
        assert row.repo_path == str(repo.resolve())
        assert row.user_id == "web_ws_u1"
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()


def test_reject_unsafe_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path / "allowed"))
    get_settings.cache_clear()
    try:
        (tmp_path / "allowed").mkdir(parents=True, exist_ok=True)
        evil = tmp_path / "outside"
        evil.mkdir()
        with pytest.raises(ValueError, match="allowed"):
            validate_workspace_path(str(evil))
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()
