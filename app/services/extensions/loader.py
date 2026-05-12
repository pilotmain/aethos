# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Optional extension modules (Open Core vs paid add-ons).

Core never requires ``nexa_ext.*`` to exist. Install ``nexa-ext-pro`` (or mount a layer)
that registers implementations under the ``nexa_ext`` namespace.

Example::

    # pip package nexa-ext-pro → module nexa_ext.sandbox
    sandbox = get_extension("sandbox")
    if sandbox is not None and hasattr(sandbox, "run_in_sandbox"):
        sandbox.run_in_sandbox(mode, fn)
    else:
        fn()
"""

from __future__ import annotations

import importlib
import re
import sys
from types import ModuleType

_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _normalize_extension_name(name: str) -> str | None:
    n = (name or "").strip().lower()
    if not n or not _SAFE_NAME.match(n):
        return None
    return n


def get_extension(name: str) -> ModuleType | None:
    """
    Import ``nexa_ext.<name>`` if installed; otherwise return ``None``.

    Callers must fall back to OSS behavior when this returns ``None``.
    """
    safe = _normalize_extension_name(name)
    if safe is None:
        return None
    try:
        return importlib.import_module(f"nexa_ext.{safe}")
    except ImportError:
        return None


def extension_loaded(name: str) -> bool:
    """Whether ``nexa_ext.<name>`` imported successfully at least once."""
    safe = _normalize_extension_name(name)
    if safe is None:
        return False
    mod_name = f"nexa_ext.{safe}"
    return mod_name in sys.modules and sys.modules[mod_name] is not None


__all__ = ["extension_loaded", "get_extension"]
