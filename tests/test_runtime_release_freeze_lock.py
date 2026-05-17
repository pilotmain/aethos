# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_release_freeze_lock import build_runtime_release_freeze_lock


def test_release_freeze() -> None:
    out = build_runtime_release_freeze_lock()["runtime_release_freeze_lock"]
    assert out["runtime_frozen"] is True
    assert out["enterprise_runtime_locked"] is True
