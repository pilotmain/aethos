# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 76 — Blue-Green simulation helpers and plumbing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.host_executor import build_simulation_plan, _git_status_short_paths


def test_build_simulation_plan_git_commit_includes_message_and_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_short(_p: Path, *, timeout: int = 15):
        return {"paths": ["foo.py", "bar.md"], "error": None}

    monkeypatch.setattr(
        "app.services.host_executor._git_status_short_paths",
        fake_short,
    )
    plan = build_simulation_plan(
        {
            "host_action": "git_commit",
            "commit_message": "wip",
            "cwd_relative": ".",
        }
    )
    assert plan["action"] == "git_commit"
    assert plan["fields"]["commit_message"] == "wip"
    assert plan["fields"]["changed_files"] == ["foo.py", "bar.md"]


def test_git_status_short_paths_skips_when_sandbox_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = type("S", (), {"nexa_simulation_sandbox_mode": False})()
    monkeypatch.setattr("app.services.host_executor._host_settings", lambda: fake)
    out = _git_status_short_paths(tmp_path)
    assert out["error"] == "sandbox_probes_disabled"
    assert out["paths"] == []
