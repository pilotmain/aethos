"""Phase 9 — plugin registry and dynamic tool registration."""

from __future__ import annotations

from app.services.plugins.registry import PLUGINS, load_plugins, plugin_manifest
from app.services.tools.registry import TOOLS


def test_load_plugins_registers_builtin_tools():
    load_plugins()
    assert "web_search" in TOOLS
    td = TOOLS["web_search"]
    assert td.pii_policy == "firewall_required"


def test_plugin_manifest_lists_loaded_plugins():
    load_plugins()
    names = [x["name"] for x in plugin_manifest()]
    assert "builtin_tools" in names
    assert PLUGINS
