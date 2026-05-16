# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.marketplace.runtime_marketplace import marketplace_install, marketplace_upgrade


def test_upgrade_bumps_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        marketplace_install("linear-provider")
        out = marketplace_upgrade("linear-provider", version="1.1.0")
        assert out.get("version") == "1.1.0"
    finally:
        get_settings.cache_clear()
