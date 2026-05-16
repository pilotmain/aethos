# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 1 final freeze / transition gate — minimum repeated-cycle targets (≥100 each in default CI)."""

from __future__ import annotations

import os

import pytest

MIN_REPEATED_CYCLES = 100


def repeated_cycles(*, large: int = 200) -> int:
    """Return iteration count: default ``MIN_REPEATED_CYCLES``; ``AETHOS_CHURN_LARGE=1`` uses ``large``."""
    if (os.environ.get("AETHOS_CHURN_LARGE") or "").strip() == "1":
        return max(int(large), MIN_REPEATED_CYCLES)
    return MIN_REPEATED_CYCLES


def widen_runtime_event_buffer(monkeypatch: pytest.MonkeyPatch, *, limit: int = 25000) -> None:
    """Lifecycle / rollback emit many runtime events; default 500 cap breaks ≥100 churn cycles."""
    monkeypatch.setenv("AETHOS_RUNTIME_EVENT_BUFFER_LIMIT", str(limit))
    from app.core.config import get_settings

    get_settings.cache_clear()
