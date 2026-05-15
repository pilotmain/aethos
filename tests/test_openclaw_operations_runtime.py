# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.operations import operations_runtime
from app.runtime.runtime_state import load_runtime_state


def test_enqueue_operation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    rec = operations_runtime.enqueue_operation(st, "health_check", user_id="u1")
    assert rec.get("type") == "health_check"
    rows = operations_runtime.list_operations(st, user_id="u1")
    assert rows and rows[0]["operation_id"] == rec["operation_id"]
