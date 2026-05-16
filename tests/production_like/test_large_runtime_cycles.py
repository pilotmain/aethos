# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.orchestration import runtime_dispatcher
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles


@pytest.mark.production_like
def test_large_runtime_dispatch_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = repeated_cycles(large=220)
    st = load_runtime_state()
    for _ in range(n):
        runtime_dispatcher.dispatch_once(st)
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
