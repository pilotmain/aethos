# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight plugin runtime host (Phase 2 Step 8)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_registry import list_plugin_manifests


class PluginRuntime:
    """Sandbox-lite: plugins declare capabilities; execution stays in core runtime."""

    def __init__(self) -> None:
        self._started = False

    def start(self) -> None:
        self._started = True

    def status(self) -> dict[str, Any]:
        return {
            "started": self._started,
            "manifest_count": len(list_plugin_manifests()),
            "sandbox": "capability_declarations_only",
        }
