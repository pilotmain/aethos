# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 23 — end-to-end dev mission with local stub."""

from __future__ import annotations

import subprocess

from app.core.config import get_settings
from app.services.dev_runtime.service import run_dev_mission
from app.services.dev_runtime.workspace import register_workspace


def test_run_dev_mission_completes(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    get_settings.cache_clear()
    try:
        ws = register_workspace(db_session, "web_pipe_u1", "p", str(repo))
        out = run_dev_mission(db_session, "web_pipe_u1", ws.id, "Run tests and summarize", auto_pr=False)
        assert out.get("ok") is True
        assert out.get("status") == "completed"
        assert len(out.get("steps") or []) >= 3
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()
