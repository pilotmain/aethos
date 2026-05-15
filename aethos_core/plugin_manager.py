# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Optional proprietary extension loader.

This module intentionally keeps the open-source default boring: commercial
``aethos_pro`` modules are loaded only when present and explicitly enabled.
"""

from __future__ import annotations

import importlib
import os
import re
from types import ModuleType
from typing import Any

_PLUGIN_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class PluginManager:
    """Best-effort loader for optional ``aethos_pro`` modules."""

    @staticmethod
    def is_pro_available() -> bool:
        """Return ``True`` only when pro extensions are enabled and importable."""
        enabled = str(os.getenv("AETHOS_PRO_ENABLED", "")).strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return False
        try:
            importlib.import_module("aethos_pro")
        except ImportError:
            return False
        return True

    @staticmethod
    def load_proprietary(name: str, fallback: Any = None) -> ModuleType | Any:
        """Load ``aethos_pro.<name>`` if available; otherwise return ``fallback``."""
        if not isinstance(name, str) or not _PLUGIN_NAME_RE.fullmatch(name):
            return fallback
        if not PluginManager.is_pro_available():
            return fallback
        try:
            return importlib.import_module(f"aethos_pro.{name}")
        except ImportError:
            return fallback


__all__ = ["PluginManager"]
