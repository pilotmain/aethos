# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.soak
def test_repeated_load_save_keeps_integrity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    cycles = 120 if os.environ.get("AETHOS_SOAK_LONG") == "1" else 35
    for i in range(cycles):
        st = load_runtime_state()
        m = st.setdefault("runtime_metrics", {})
        if isinstance(m, dict):
            m["soak_touch"] = int(m.get("soak_touch") or 0) + 1
        save_runtime_state(st)
    inv = validate_runtime_state(load_runtime_state())
    assert inv.get("ok") is True
