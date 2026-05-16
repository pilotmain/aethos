# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_many_runtime_save_load_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    cycles = 150 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 105
    st = load_runtime_state()
    for _ in range(cycles):
        save_runtime_state(st)
        st = load_runtime_state()
    assert validate_runtime_state(st).get("ok") is True
