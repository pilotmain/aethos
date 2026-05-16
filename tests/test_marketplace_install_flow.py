# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.marketplace.runtime_marketplace import marketplace_install, marketplace_uninstall


def test_marketplace_install_linear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        out = marketplace_install("linear-provider")
        assert out.get("plugin_id") == "linear-provider"
        marketplace_uninstall("linear-provider")
    finally:
        get_settings.cache_clear()
