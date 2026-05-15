# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Long-running / execution queue shell fields in runtime JSON."""

from __future__ import annotations

from app.runtime.runtime_state import default_runtime_state


def test_default_runtime_has_execution_shells() -> None:
    st = default_runtime_state()
    assert isinstance(st.get("tasks"), list)
    assert isinstance(st.get("execution_queue"), list)
    assert isinstance(st.get("long_running"), list)
