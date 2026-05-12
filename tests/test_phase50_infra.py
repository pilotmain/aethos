# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 50 — CLI token env + dev workspace mirror."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.infra.cli_env import cli_auth_env


def test_cli_auth_env_injects_tokens(monkeypatch) -> None:
    monkeypatch.setenv("RAILWAY_TOKEN", "rt-test")
    monkeypatch.setenv("VERCEL_TOKEN", "vt-test")
    env = cli_auth_env()
    assert env.get("RAILWAY_TOKEN") == "rt-test"
    assert env.get("VERCEL_TOKEN") == "vt-test"


def test_register_dev_workspace_after_root(db_session, tmp_path: Path) -> None:
    from app.services.dev_runtime.workspace import register_dev_workspace_for_registry_root
    from app.services.workspace_registry import add_root

    uid = "u_phase50"
    p = tmp_path / "proj"
    p.mkdir()
    row = add_root(db_session, uid, str(p))
    dw = register_dev_workspace_for_registry_root(db_session, uid, row.path_normalized)
    assert dw is not None
    assert dw.repo_path == row.path_normalized
