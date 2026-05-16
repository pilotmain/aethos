# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_slice_persistence import (
    load_persisted_slices,
    persist_truth_slices,
    slice_persistence_health,
)


def test_slice_persistence_roundtrip() -> None:
    persist_truth_slices({"enterprise_overview": {"phase": "test"}}, user_id="u_persist")
    loaded = load_persisted_slices("u_persist")
    assert "enterprise_overview" in loaded
    health = slice_persistence_health("u_persist")
    assert health["integrity_validated"] is True
