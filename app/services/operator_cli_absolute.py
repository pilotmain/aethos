"""
Optional absolute paths for operator CLIs when PATH / login-shell resolution fails.

Configure ``NEXA_OPERATOR_CLI_*_ABS`` to full binaries from ``which vercel`` / ``which gh``
on the **worker** filesystem. Reads ``os.environ`` first (Docker ``-e``, systemd), then
:class:`~app.core.config.Settings`, so injected vars apply even if ``.env`` is missing.

Set ``NEXA_OPERATOR_CLI_ABS_DEBUG=1`` to log whether each configured path exists and is executable.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.services.operator_cli_path import which_operator_cli

logger = logging.getLogger(__name__)

_SHORT_TO_ATTR: dict[str, str] = dict(
    (
        ("vercel", "nexa_operator_cli_vercel_abs"),
        ("gh", "nexa_operator_cli_gh_abs"),
        ("git", "nexa_operator_cli_git_abs"),
        ("railway", "nexa_operator_cli_railway_abs"),
    )
)

# Explicit env keys (must match Pydantic Settings env names).
_CLI_ENV_KEYS: dict[str, str] = {
    "vercel": "NEXA_OPERATOR_CLI_VERCEL_ABS",
    "gh": "NEXA_OPERATOR_CLI_GH_ABS",
    "git": "NEXA_OPERATOR_CLI_GIT_ABS",
    "railway": "NEXA_OPERATOR_CLI_RAILWAY_ABS",
}


def _abs_debug_enabled() -> bool:
    return (os.environ.get("NEXA_OPERATOR_CLI_ABS_DEBUG") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _configured_absolute_raw(short: str) -> str:
    """
    Non-empty path string from ``os.environ`` (preferred) or Settings.

    Workers often receive CLI paths only via the process environment (Docker, supervisor),
    not from a repo-root ``.env`` file loaded by Pydantic.
    """
    env_key = _CLI_ENV_KEYS.get(short)
    if env_key:
        v = (os.environ.get(env_key) or "").strip()
        if v:
            return v
    attr = _SHORT_TO_ATTR.get(short)
    if not attr:
        return ""
    try:
        from app.core.config import get_settings

        return (getattr(get_settings(), attr, None) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def apply_operator_cli_absolute_fallback(argv: list[str]) -> list[str]:
    """
    If a configured absolute path exists for ``argv[0]``'s basename and the file is executable,
    replace argv[0] with that path. Otherwise return the same list object when unchanged.
    """
    if not argv:
        return argv
    base = Path(argv[0]).name
    raw = _configured_absolute_raw(base)
    if not raw:
        return argv
    p = Path(raw).expanduser()
    exists = False
    executable = False
    try:
        exists = p.is_file()
        executable = bool(exists and os.access(p, os.X_OK))
        if _abs_debug_enabled():
            logger.info(
                "[operator_cli_absolute] %s: path=%s exists=%s executable=%s",
                base,
                raw,
                exists,
                executable,
            )
        if executable:
            before = list(argv)
            out = list(argv)
            out[0] = str(p.resolve())
            if _abs_debug_enabled():
                logger.info(
                    "[operator_cli_absolute] Rewriting argv: %r -> %r",
                    before,
                    out,
                )
            return out
    except OSError as exc:
        if _abs_debug_enabled():
            logger.info(
                "[operator_cli_absolute] %s: path=%s error=%s",
                base,
                raw,
                exc,
            )
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
