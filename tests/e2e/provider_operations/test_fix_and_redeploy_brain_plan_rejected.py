# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.providers.repair.repair_plan_validation import validate_repair_plan


def test_invalid_brain_plan_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    plan = {"steps": [{"type": "shell", "command": "rm -rf /"}]}
    out = validate_repair_plan(plan, repo_path=repo)
    assert out["valid"] is False
