# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Memory store parity — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §7."""

from __future__ import annotations

from app.services.memory.memory_store import MemoryStore


def test_memory_store_list_entries_empty_ok(tmp_path) -> None:
    st = MemoryStore(base_dir=tmp_path)
    assert st.list_entries("parity_mem_u1") == []
