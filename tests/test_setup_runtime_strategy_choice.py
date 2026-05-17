# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_routing import CANONICAL_ROUTING_MODES, build_routing_env_updates


def test_canonical_routing_modes_match_spec() -> None:
    labels = {m["label"] for m in CANONICAL_ROUTING_MODES.values()}
    assert "Local-first" in labels
    assert "Cloud-first" in labels
    assert "Hybrid" in labels
    assert "Manual routing" in labels


def test_hybrid_env_updates_local_first_flag() -> None:
    updates = build_routing_env_updates("hybrid", preference="balanced")
    assert updates["AETHOS_ROUTING_MODE"] == "hybrid"
    assert updates["AETHOS_LOCAL_FIRST"] == "true"
    assert updates["AETHOS_LOCAL_ONLY"] == "false"
