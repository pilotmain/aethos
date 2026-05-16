# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.projects.project_registry_service import link_project_repo, resolve_project_slug


def test_resolve_project_slug_exact_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        link_project_repo("invoicepilot", str(tmp_path / "repo"), persist=True)
        pid, cands = resolve_project_slug("invoicepilot")
        assert pid == "invoicepilot"
        assert len(cands) == 1
    finally:
        get_settings.cache_clear()
