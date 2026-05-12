# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73d — graceful API restart after a self-improvement merge lands.

Five methods are supported, picked by
``Settings.nexa_self_improvement_auto_restart_method``:

==================  ==============================================================
``uvicorn-reload``  Touch ``app/_reload_sentinel.py`` so a uvicorn ``--reload``
                    worker picks up the new code in-process. Dev-friendly
                    default — does not exit the process. **Requires the API to
                    have been started with ``uvicorn --reload``.**
``systemd``         ``sys.exit(0)`` after a flush delay; assumes a systemd unit
                    with ``Restart=always``.
``docker``          ``sys.exit(0)`` after a flush delay; assumes a container
                    restart policy (e.g. ``--restart=always``).
``supervisor``      ``sys.exit(0)`` after a flush delay; assumes ``autorestart=true``.
``noop`` (default)  Log a warning and do nothing. Operator restarts manually.
==================  ==============================================================

The master switch ``Settings.nexa_self_improvement_auto_restart`` MUST also
be true; otherwise :func:`restart_api` is a guarded no-op.

API endpoints in :mod:`app.api.routes.self_improvement` use this module via
:func:`schedule_restart`, which always returns the response to the client
*before* the underlying restart action runs (so the operator sees a clean
``{"status":"restarting"}`` payload instead of a connection-reset).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


VALID_METHODS = {"uvicorn-reload", "systemd", "docker", "supervisor", "noop"}

# Path to the sentinel module the uvicorn-reload method touches. We use a
# tiny dedicated module so we don't have to touch a real source file (which
# would be visible in `git status` and could accidentally be committed).
SENTINEL_PATH = Path(__file__).resolve().parent.parent / "_reload_sentinel.py"
SENTINEL_TEMPLATE = '''"""
Phase 73d sentinel module — touched by app.core.restart to trigger
uvicorn --reload to re-import the application. Don't import from this
module; its only job is to have its mtime bumped.
"""

# Last touched: {ts}
TOUCHED_AT = "{ts}"
'''


# --- Public surface -------------------------------------------------------


def restart_enabled() -> bool:
    """Resolve at request time so settings overrides in tests work."""
    s = get_settings()
    return bool(getattr(s, "nexa_self_improvement_auto_restart", False))


def restart_method() -> str:
    s = get_settings()
    m = str(getattr(s, "nexa_self_improvement_auto_restart_method", "noop") or "noop").lower()
    return m if m in VALID_METHODS else "noop"


def perform_restart() -> dict[str, str]:
    """Execute the restart synchronously. Returns a status dict.

    *Never* call this directly from a request handler — use
    :func:`schedule_restart` so the response flushes first.
    """
    if not restart_enabled():
        logger.warning("perform_restart called but auto_restart=false; ignoring")
        return {"status": "disabled", "method": restart_method()}
    method = restart_method()
    logger.info("perform_restart method=%s", method)
    if method == "uvicorn-reload":
        try:
            _touch_sentinel()
            return {"status": "reloaded", "method": method, "sentinel": str(SENTINEL_PATH)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("uvicorn-reload sentinel touch failed: %s", exc)
            return {"status": "failed", "method": method, "error": str(exc)}
    if method in {"systemd", "docker", "supervisor"}:
        # Sleep is provided by schedule_restart's wrapper; this just exits.
        logger.warning("perform_restart: exiting process for %s restart", method)
        # Use os._exit so atexit hooks don't accidentally block — under a
        # supervisor we want to be replaced quickly.
        os._exit(0)  # noqa: SLF001 — intentional immediate exit
    if method == "noop":
        logger.info("perform_restart: noop method; operator must restart manually")
        return {"status": "noop", "method": method}
    logger.warning("perform_restart: unknown method=%r; ignoring", method)
    return {"status": "unknown_method", "method": method}


async def schedule_restart(*, delay_s: float = 1.0) -> dict[str, str]:
    """Schedule :func:`perform_restart` to run after ``delay_s`` seconds.

    Designed to be called from a request handler so the response can flush
    before the process exits. Returns a small JSON-serialisable dict the
    caller can return to the client immediately.
    """
    if not restart_enabled():
        return {
            "status": "disabled",
            "method": restart_method(),
            "detail": "NEXA_SELF_IMPROVEMENT_AUTO_RESTART is false",
        }
    method = restart_method()
    if method == "noop":
        return {"status": "noop", "method": method}
    # Fire-and-forget: don't await it, so the calling request returns now.
    loop = asyncio.get_running_loop()
    loop.call_later(delay_s, perform_restart)
    return {"status": "scheduled", "method": method, "delay_s": delay_s}


# --- Helpers --------------------------------------------------------------


def _touch_sentinel() -> None:
    """Write a tiny module so uvicorn ``--reload`` picks up a change.

    We rewrite the file content (not just the mtime) so reload triggers on
    file-system watchers that key off content-hash rather than mtime.
    """
    ts = datetime.now(timezone.utc).isoformat()
    SENTINEL_PATH.write_text(SENTINEL_TEMPLATE.format(ts=ts), encoding="utf-8")


# Kept for backwards-compat with the spec snippets in PHASE73C; not used
# directly by any route.
def restart_api() -> dict[str, str]:
    """Synchronous shim around :func:`perform_restart`."""
    return perform_restart()


__all__ = [
    "VALID_METHODS",
    "perform_restart",
    "restart_api",
    "restart_enabled",
    "restart_method",
    "schedule_restart",
]


# Quiet unused-import if `sys` ever gets removed by an over-eager linter.
_ = sys
