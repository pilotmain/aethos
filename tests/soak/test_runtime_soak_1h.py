# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded soak loop (full 1h-style soak is opt-in via AETHOS_SOAK_LONG=1)."""

from __future__ import annotations

import os

import pytest

from app.orchestration import runtime_dispatcher
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.soak
def test_runtime_load_dispatch_stays_valid(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = 400 if os.environ.get("AETHOS_SOAK_LONG") == "1" else 60
    for _ in range(n):
        st = load_runtime_state()
        runtime_dispatcher.dispatch_once(st)
        save_runtime_state(st)
    stf = load_runtime_state()
    inv = validate_runtime_state(stf)
    assert inv.get("ok") is True
