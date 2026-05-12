# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 39 — heartbeat scheduler hook."""

from __future__ import annotations

from unittest.mock import patch

from app.services.scheduler.heartbeat import run_heartbeat_cycle


def test_heartbeat_skipped_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_HEARTBEAT_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        out = run_heartbeat_cycle()
        assert out.get("skipped") == "disabled"
    finally:
        get_settings.cache_clear()


def test_heartbeat_emits_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_HEARTBEAT_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("app.services.scheduler.heartbeat.emit_runtime_event") as em:
            out = run_heartbeat_cycle()
        assert out.get("ok") is True
        em.assert_called_once()
    finally:
        get_settings.cache_clear()
