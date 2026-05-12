# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.providers.local_runtime_catalog import list_local_runtimes


def test_catalog_lists_known_runtimes() -> None:
    rows = list_local_runtimes()
    ids = {r["id"] for r in rows}
    assert "ollama" in ids
    assert "generic_openai_compat" in ids
