# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Example plugin — registers tool descriptors (execution still goes through provider gateway)."""

from __future__ import annotations

from app.services.plugins.registry import PluginRegistry, register_plugin


class BuiltinToolsPlugin:
    name = "builtin_tools"

    def register(self, registry: PluginRegistry) -> None:
        registry.add_tool(
            {
                "name": "web_search",
                "description": "Web search (privacy-scrubbed payloads only)",
                "provider": "local_stub",
                "pii_policy": "firewall_required",
                "risk_level": "model",
            }
        )


register_plugin(BuiltinToolsPlugin())
