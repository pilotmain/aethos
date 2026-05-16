# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.projects.project_discovery import discover_local_projects


def test_discover_local_projects_finds_package_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    scan_root = tmp_path / "scan"
    app_dir = scan_root / "svc"
    app_dir.mkdir(parents=True)
    (app_dir / "package.json").write_text(json.dumps({"name": "InvoicePilot"}), encoding="utf-8")
    monkeypatch.setenv("AETHOS_PROJECT_SEARCH_ROOTS", str(scan_root))
    monkeypatch.setenv("AETHOS_PROJECT_DISCOVERY_DEPTH", "4")
    get_settings.cache_clear()
    try:
        rows = discover_local_projects(max_candidates=50)
    finally:
        get_settings.cache_clear()
    assert len(rows) >= 1
    row = next(r for r in rows if r.get("name") == "InvoicePilot")
    assert row.get("project_id") == "invoicepilot"
    assert Path(row["repo_path"]).resolve() == app_dir.resolve()
