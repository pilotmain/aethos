# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""FastAPI lifespan hooks for persistent runtime parity (``~/.aethos/aethos.json``)."""

from __future__ import annotations

import logging
import os

_LOG = logging.getLogger("aethos.runtime")


def _bind_host() -> str:
    return (os.environ.get("AETHOS_RUNTIME_HOST") or "0.0.0.0").strip() or "0.0.0.0"


def _bind_port() -> int:
    for key in ("AETHOS_RUNTIME_PORT", "PORT", "NEXA_SERVE_PORT", "AETHOS_SERVE_PORT"):
        v = (os.environ.get(key) or "").strip()
        if v.isdigit():
            return int(v)
    return 8010


def _skip_runtime_hooks() -> bool:
    if (os.environ.get("AETHOS_RUNTIME_ENABLE_IN_PYTEST") or "").strip().lower() in ("1", "true", "yes"):
        return False
    return (os.environ.get("NEXA_PYTEST") or "").strip().lower() in ("1", "true", "yes")


def lifespan_runtime_start() -> None:
    if _skip_runtime_hooks():
        return
    try:
        from app.runtime.runtime_workspace import ensure_runtime_workspace_layout
        from app.runtime.runtime_recovery import boot_prepare_runtime_state
        from app.runtime.runtime_heartbeat import start_heartbeat_background

        ensure_runtime_workspace_layout()
        boot_prepare_runtime_state(host=_bind_host(), port=_bind_port())
        start_heartbeat_background()
        _LOG.info("runtime_parity.started port=%s", _bind_port())
    except Exception as exc:
        _LOG.warning("runtime_parity.start_failed %s", exc)


def lifespan_runtime_stop() -> None:
    try:
        from app.runtime.runtime_heartbeat import stop_heartbeat_background
        from app.runtime.runtime_state import mark_gateway_stopped

        stop_heartbeat_background()
        mark_gateway_stopped()
        _LOG.info("runtime_parity.stopped")
    except Exception as exc:
        _LOG.warning("runtime_parity.stop_failed %s", exc)
