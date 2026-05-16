# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.deploy_context.nl_resolution import extract_project_slug_from_phrase
from app.projects.project_registry_service import link_project_repo
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_extract_slug_from_registry(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        link_project_repo("invoicepilot", str(tmp_path / "repo"), persist=True)
        pid, cands = extract_project_slug_from_phrase("invoicepilot")
        assert pid == "invoicepilot"
        assert len(cands) == 1
    finally:
        get_settings.cache_clear()
