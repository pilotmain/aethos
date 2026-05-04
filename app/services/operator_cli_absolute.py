"""
Backward-compatible shim for CLI argv resolution.

Canonical logic lives in :mod:`app.services.cli_backends` (:func:`~app.services.cli_backends.get_cli_command`).
"""

from __future__ import annotations

import os
from pathlib import Path

from app.services.cli_backends import get_cli_command
from app.services.operator_cli_path import which_operator_cli

__all__ = [
    "apply_operator_cli_absolute_fallback",
    "operator_cli_argv_resolves",
]


def apply_operator_cli_absolute_fallback(argv: list[str]) -> list[str]:
    """Resolve ``argv[0]`` via CLI backends (configured absolute path → PATH)."""
    if not argv:
        return argv
    base = Path(argv[0]).name
    return get_cli_command(base, list(argv[1:]))


def operator_cli_argv_resolves(argv: list[str]) -> bool:
    """True when the resolved executable exists or appears on the enriched operator PATH."""
    if not argv:
        return False
    raw0 = Path(argv[0]).expanduser()
    try:
        if raw0.is_file() and os.access(raw0, os.X_OK):
            return True
    except OSError:
        pass
    base = Path(argv[0]).name
    resolved = get_cli_command(base, [])[0]
    p = Path(resolved).expanduser()
    try:
        if p.is_file() and os.access(p, os.X_OK):
            return True
    except OSError:
        pass
    return which_operator_cli(base) is not None
