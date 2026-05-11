"""Optional ``aethos_pro.*`` plugin loader — mirrors the ``nexa_ext.*`` pattern (see docs/OPEN_CORE_EXTENSIONS.md)."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any


class PluginManager:
    """Load proprietary extensions when the ``aethos_pro`` distribution is installed."""

    @staticmethod
    def load_proprietary(module_name: str, fallback: Any | None = None) -> Any | None:
        """
        Try ``import aethos_pro.<module_name>``; return ``fallback`` on failure.

        ``module_name`` must be a single dotted segment (e.g. ``goal_planner``), not nested paths.
        """
        if not module_name or "." in module_name:
            return fallback
        fq = f"aethos_pro.{module_name}"
        try:
            spec = importlib.util.find_spec(fq)
            if spec is not None:
                return importlib.import_module(fq)
        except ImportError:
            pass
        return fallback

    @staticmethod
    def is_pro_available() -> bool:
        """True when the ``aethos_pro`` package is importable (commercial wheel / private index)."""
        try:
            importlib.import_module("aethos_pro")
            return True
        except ImportError:
            return False


__all__ = ["PluginManager"]
