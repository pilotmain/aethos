# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cross-cutting structured log lines for major subsystems (Phase 28)."""

from __future__ import annotations

import json
from typing import Any

from app.services.logging.logger import get_logger

_log = get_logger("system_event")


def log_system_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
    """
    Emit a single INFO log line for audits / observability hooks.

    Prefer domain-specific ``emit_runtime_event`` when publishing to the Mission Control bus;
    use this for deployment diagnostics and subsystem breadcrumbs.
    """
    safe = payload or {}
    try:
        tail = json.dumps(safe, default=str)[:4000]
    except Exception:
        tail = str(safe)[:4000]
    _log.info("system_event type=%s payload=%s", event_type, tail)
