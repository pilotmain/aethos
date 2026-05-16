# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

from app.providers.repair.repair_planner import build_deterministic_repair_plan


def test_planner_includes_verify_and_redeploy(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"scripts": {"build": "next build"}}), encoding="utf-8")
    repair_ctx = {"repair_context_id": "r1", "project_id": "acme", "diagnosis": {"failure_category": "build_failure"}}
    deploy_ctx = {"repo_path": str(repo), "provider": "vercel"}
    plan = build_deterministic_repair_plan(repair_context=repair_ctx, deploy_ctx=deploy_ctx)
    types = [s["type"] for s in plan.get("steps") or []]
    assert "inspect" in types
    assert "verify" in types
    assert "redeploy" in types
