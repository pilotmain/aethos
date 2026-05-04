"""
Optional absolute paths for operator CLIs when PATH / login-shell resolution fails.

Configure ``NEXA_OPERATOR_CLI_*_ABS`` to full binaries from ``which vercel`` / ``which gh``
on the worker host. argv is still built only from Nexa allowlists; only argv[0] is rewritten.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.services.operator_cli_path import which_operator_cli

_NAME_TO_SETTING_ATTR: tuple[tuple[str, str], ...] = (
    ("vercel", "nexa_operator_cli_vercel_abs"),
    ("gh", "nexa_operator_cli_gh_abs"),
    ("git", "nexa_operator_cli_git_abs"),
    ("railway", "nexa_operator_cli_railway_abs"),
)


def apply_operator_cli_absolute_fallback(argv: list[str]) -> list[str]:
    """
    If settings provide an absolute path for ``argv[0]``'s basename and the file is executable,
    replace argv[0] with that path. Otherwise return the same list (possibly copied only when needed).
    """
    if not argv:
        return argv
    base = Path(argv[0]).name
    try:
        from app.core.config import get_settings

        s = get_settings()
    except Exception:  # noqa: BLE001
        return argv

    for short, attr in _NAME_TO_SETTING_ATTR:
        if base != short:
            continue
        raw = (getattr(s, attr, None) or "").strip()
        if not raw:
            return argv
        p = Path(raw).expanduser()
        try:
            if p.is_file() and os.access(p, os.X_OK):
                out = list(argv)
                out[0] = str(p.resolve())
                return out
        except OSError:
            return argv
        return argv

    return argv


def operator_cli_argv_resolves(argv: list[str]) -> bool:
    """
    True if argv[0] can be executed: existing executable file, or basename found on enriched PATH.
    """
    if not argv:
        return False
    raw = argv[0]
    p = Path(raw).expanduser()
    try:
        if p.is_file() and os.access(p, os.X_OK):
            return True
    except OSError:
        pass
    return which_operator_cli(p.name) is not None


__all__ = [
    "apply_operator_cli_absolute_fallback",
    "operator_cli_argv_resolves",
]
