# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles


@pytest.mark.production_like
def test_many_runtime_save_load_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    cycles = max(105, repeated_cycles(large=250))
    st = load_runtime_state()
    for _ in range(cycles):
        save_runtime_state(st)
        st = load_runtime_state()
    assert validate_runtime_state(st).get("ok") is True
