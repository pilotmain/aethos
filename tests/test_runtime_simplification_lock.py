# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_simplification_lock import build_runtime_simplification_lock


def test_runtime_simplification_lock_locked() -> None:
    out = build_runtime_simplification_lock({})
    lock = out["runtime_simplification_lock"]
    assert lock.get("locked") is True
    assert lock.get("canonical_systems")
