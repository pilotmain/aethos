# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.providers.repair.repair_execution import execute_repair_plan


def test_execute_repair_plan_mocked_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text("{}", encoding="utf-8")
    deploy_ctx = {"repo_path": str(repo.resolve())}
    plan = {
        "plan_id": "p1",
        "steps": [
            {"type": "inspect", "target": "package.json"},
            {"type": "redeploy", "provider": "vercel"},
        ],
    }
    monkeypatch.setattr(
        "app.providers.repair.repair_execution.run_verification_suite",
        lambda _p: {"ok": True, "results": []},
    )
    out = execute_repair_plan(plan, deploy_ctx=deploy_ctx)
    assert out.get("ok") is True
