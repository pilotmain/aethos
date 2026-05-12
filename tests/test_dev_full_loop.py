# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 42 — dev mission retries until tests pass (bounded)."""

from __future__ import annotations

import subprocess

import pytest

from app.core.config import get_settings
from app.services.dev_runtime.service import DEV_PIPELINE_SEQUENCE
from app.services.dev_runtime.service import run_dev_mission
from app.services.dev_runtime.workspace import register_workspace


def test_run_dev_mission_retries_until_tests_pass(db_session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "full_loop"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    get_settings.cache_clear()

    n = [0]

    def flaky_then_pass(_repo):
        n[0] += 1
        if n[0] < 2:
            return {"ok": False, "summary": "fail", "parsed": {}, "command_result": {"ok": False}}
        return {"ok": True, "summary": "ok", "parsed": {}, "command_result": {"ok": True}}

    monkeypatch.setattr("app.services.dev_runtime.service.run_repo_tests", flaky_then_pass)

    try:
        ws = register_workspace(db_session, "full_loop_u", "p", str(repo))
        out = run_dev_mission(
            db_session,
            "full_loop_u",
            ws.id,
            "parity goal",
            preferred_agent="local_stub",
            max_iterations=5,
        )
        assert out.get("ok") is True
        assert out.get("tests_passed") is True
        assert out.get("iterations") == 2
        pipe = out.get("pipeline") or {}
        assert pipe.get("sequence") == list(DEV_PIPELINE_SEQUENCE)
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()
