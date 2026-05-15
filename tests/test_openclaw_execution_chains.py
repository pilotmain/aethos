# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_chain import advance_chain_cursor, create_chain, get_chain
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_execution_chain_persist_and_advance(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    cid = create_chain(st, ["t-a", "t-b"])
    save_runtime_state(st)
    st2 = load_runtime_state()
    ch = get_chain(st2, cid)
    assert ch and ch["cursor"] == 0
    advance_chain_cursor(st2, cid)
    advance_chain_cursor(st2, cid)
    save_runtime_state(st2)
    st3 = load_runtime_state()
    ch3 = get_chain(st3, cid)
    assert ch3["cursor"] == 2
    assert ch3["status"] == "completed"
