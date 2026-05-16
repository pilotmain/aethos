# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

from app.providers.repair.repair_evidence import collect_repair_evidence


def test_collect_repair_evidence_shapes(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"scripts": {"build": "x"}}), encoding="utf-8")
    deploy_ctx = {"repo_path": str(repo), "provider": "vercel", "confidence_signals": ["package.json"]}
    repair_ctx = {"diagnosis": {"failure_category": "build_failure"}}
    ev = collect_repair_evidence(
        project_id="acme",
        deploy_ctx=deploy_ctx,
        repair_context=repair_ctx,
        logs_summary="Error: build failed",
    )
    assert ev["project_id"] == "acme"
    assert ev["failure_category"] == "build_failure"
    assert ev["privacy"]["scanned"] is True
    assert "package.json" in (ev.get("workspace_files") or [])
