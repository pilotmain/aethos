# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin manifest schema (Phase 2 Step 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginManifest:
    plugin_id: str
    name: str
    version: str = "1.0.0"
    author: str = "aethos"
    capabilities: list[str] = field(default_factory=list)
    runtime_hooks: list[str] = field(default_factory=list)
    ui_hooks: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    verified: bool = False
    installed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "author": self.author,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "runtime_hooks": list(self.runtime_hooks),
            "ui_hooks": list(self.ui_hooks),
            "permissions": list(self.permissions),
            "verified": self.verified,
            "installed": self.installed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        return cls(
            plugin_id=str(data.get("plugin_id") or data.get("name") or "unknown"),
            name=str(data.get("name") or data.get("plugin_id") or "unknown"),
            version=str(data.get("version") or "1.0.0"),
            author=str(data.get("author") or "aethos"),
            capabilities=[str(x) for x in (data.get("capabilities") or [])],
            runtime_hooks=[str(x) for x in (data.get("runtime_hooks") or [])],
            ui_hooks=[str(x) for x in (data.get("ui_hooks") or [])],
            permissions=[str(x) for x in (data.get("permissions") or [])],
            verified=bool(data.get("verified")),
            installed=bool(data.get("installed", True)),
        )
