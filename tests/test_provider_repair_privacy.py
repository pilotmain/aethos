# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.providers.repair.fix_and_redeploy import run_fix_and_redeploy


def test_repair_privacy_block(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            "app.providers.repair.fix_and_redeploy._privacy_allows",
            lambda _t: (False, "blocked"),
        )
        out = run_fix_and_redeploy("acme", raw_text="fix acme")
        assert out.get("success") is False
        assert "privacy" in (out.get("summary") or "").lower() or "block" in (out.get("summary") or "").lower()
    finally:
        get_settings.cache_clear()
