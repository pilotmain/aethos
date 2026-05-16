# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.plugins.plugin_installer import install_plugin, list_installed_plugin_ids, uninstall_plugin


def test_install_to_plugins_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        manifest = {
            "plugin_id": "test-pack",
            "name": "Test Pack",
            "version": "1.0.0",
            "permissions": ["runtime.test"],
            "trust_tier": "community",
        }
        out = install_plugin(manifest)
        assert out.get("installed") is True
        assert (home / "plugins" / "test-pack" / "manifest.json").is_file()
        assert "test-pack" in list_installed_plugin_ids()
        uninstall_plugin("test-pack")
        assert "test-pack" not in list_installed_plugin_ids()
    finally:
        get_settings.cache_clear()
