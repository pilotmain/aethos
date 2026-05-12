# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 14 — graph_builder memoization."""

from __future__ import annotations

from unittest.mock import patch

from app.services.mission_control.graph_builder import (
    build_graph_cached,
    clear_graph_cache,
)


def test_build_graph_cached_second_call_skips_recompute() -> None:
    state = {
        "tasks": [
            {
                "mission_id": "m1",
                "agent_handle": "a",
                "role": "Lead",
                "status": "running",
                "depends_on": [],
            },
        ]
    }
    clear_graph_cache()
    with patch("app.services.mission_control.graph_builder.build_graph") as mocked:
        mocked.return_value = {"nodes": [{"id": "x"}], "edges": []}
        g1 = build_graph_cached(state)
        g2 = build_graph_cached(state)
        assert mocked.call_count == 1
        assert g1 == g2


def test_clear_graph_cache_forces_next_rebuild() -> None:
    state = {"tasks": []}
    clear_graph_cache()
    with patch("app.services.mission_control.graph_builder.build_graph") as mocked:
        mocked.return_value = {"nodes": [], "edges": []}
        build_graph_cached(state)
        clear_graph_cache()
        build_graph_cached(state)
        assert mocked.call_count == 2
