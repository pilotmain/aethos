# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

from app.providers.repair.repair_plan_validation import validate_repair_plan


def test_validate_rejects_protected_edit(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    plan = {
        "diagnosis": "x",
        "confidence": 0.8,
        "steps": [{"type": "edit", "path": ".env", "operation": "replace", "content": "x=1"}],
        "redeploy_after_verify": False,
    }
    out = validate_repair_plan(plan, repo_path=repo)
    assert out["valid"] is False
    assert any("protected" in e for e in out["errors"])


def test_validate_accepts_verify_step(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    plan = {
        "diagnosis": "x",
        "confidence": 0.8,
        "steps": [{"type": "verify", "command": "npm run build"}],
        "redeploy_after_verify": True,
    }
    out = validate_repair_plan(plan, repo_path=repo)
    assert out["valid"] is True
    assert out["normalized_steps"][0]["type"] == "verify"
