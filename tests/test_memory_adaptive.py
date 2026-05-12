# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 45D — memory weight file boosts successful entry ids."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.autonomy.intelligence import load_memory_weights, update_memory_weights


def test_memory_weights_boost_and_decay(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        update_memory_weights("u_mem", {"success": True, "entry_ids": ["e1"]})
        w1 = load_memory_weights("u_mem")
        assert w1.get("e1", 0) > 1.0
        update_memory_weights("u_mem", {"success": False, "entry_ids": ["e1"]})
        w2 = load_memory_weights("u_mem")
        assert w2["e1"] < w1["e1"]
    finally:
        monkeypatch.delenv("NEXA_MEMORY_DIR", raising=False)
        get_settings.cache_clear()
