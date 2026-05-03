"""Sandbox audit hooks (structured logging only)."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


def log_sandbox_decision(event: dict[str, Any]) -> None:
    safe = {k: v for k, v in event.items() if k != "secret"}
    _log.info("sandbox_decision %s", safe)


__all__ = ["log_sandbox_decision"]
