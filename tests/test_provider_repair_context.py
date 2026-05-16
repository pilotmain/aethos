# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.providers.repair.repair_context import create_repair_context, get_latest_repair_context
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_create_and_fetch_latest_repair_context(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        save_runtime_state(default_runtime_state(workspace_root=tmp_path / "ws"))
        rec = create_repair_context(
            project_id="acme",
            deploy_ctx={"repo_path": str(tmp_path), "provider": "vercel", "workspace_confidence": "high"},
            diagnosis={"failure_category": "build_failure"},
            logs_summary="err",
        )
        assert rec.get("repair_context_id")
        latest = get_latest_repair_context("acme")
        assert latest and latest.get("project_id") == "acme"
    finally:
        get_settings.cache_clear()
