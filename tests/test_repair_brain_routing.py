# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.brain.repair_brain import needs_brain_escalation, request_repair_plan_from_brain
from app.core.config import get_settings


def test_needs_brain_escalation_for_unknown() -> None:
    assert needs_brain_escalation({"failure_category": "unknown"}, {"confidence": 0.4})


def test_repair_brain_deterministic_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_PYTEST", "1")
    get_settings.cache_clear()
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"scripts": {"build": "echo ok"}}), encoding="utf-8")
    evidence = {
        "project_id": "acme",
        "repo_path": str(repo),
        "failure_category": "build_failure",
        "package_scripts": {"build": "echo ok"},
    }
    try:
        plan, decision = request_repair_plan_from_brain(evidence=evidence, project_id="acme")
        assert plan is not None
        assert decision["selected_provider"] == "deterministic"
        assert any(s.get("type") == "verify" for s in plan.get("steps") or [])
    finally:
        get_settings.cache_clear()
