"""
Phase 36 — Map ``AETHOS_*`` environment variables onto legacy ``NEXA_*`` keys.

The Python :class:`~app.core.config.Settings` model still uses internal field names
``nexa_*`` with env vars ``NEXA_*``. Setting ``AETHOS_WORKSPACE_ROOT`` (or any
``AETHOS_<SUFFIX>``) writes the same value to ``NEXA_<SUFFIX>`` before Settings
is instantiated. When both are set, **AETHOS wins**.
"""

from __future__ import annotations

import os


def apply_aethos_env_aliases() -> None:
    """Overlay ``AETHOS_*`` → ``NEXA_*`` and optional branded aliases for third-party keys."""
    for key, val in list(os.environ.items()):
        if not key.startswith("AETHOS_"):
            continue
        suffix = key[7:]
        if not suffix:
            continue
        os.environ["NEXA_" + suffix] = val

    # Sidecar flag used before Settings loads (see config.py DATABASE_URL shortcut).
    sid = (os.environ.get("AETHOS_NEXT_LOCAL_SIDECAR") or "").strip()
    if sid:
        os.environ["NEXA_NEXT_LOCAL_SIDECAR"] = sid

    # CLI / scripts read these outside pydantic (e.g. aethos_cli).
    base = (os.environ.get("AETHOS_API_BASE") or "").strip()
    if base:
        os.environ["NEXA_API_BASE"] = base.rstrip("/")

    tok = (os.environ.get("AETHOS_TELEGRAM_BOT_TOKEN") or "").strip()
    if tok:
        os.environ["TELEGRAM_BOT_TOKEN"] = tok

    key = (os.environ.get("AETHOS_OPENAI_API_KEY") or "").strip()
    if key:
        os.environ["OPENAI_API_KEY"] = key

    web_tok = (os.environ.get("AETHOS_WEB_API_TOKEN") or "").strip()
    if web_tok:
        os.environ["NEXA_WEB_API_TOKEN"] = web_tok


__all__ = ["apply_aethos_env_aliases"]
