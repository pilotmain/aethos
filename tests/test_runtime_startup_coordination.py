# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_startup_coordination import (
    build_startup_lock_status,
    release_startup_lock_if_owner,
    try_acquire_startup_lock,
)


def test_startup_lock_acquire_release(tmp_path, monkeypatch) -> None:
    lock = tmp_path / "startup.lock"
    monkeypatch.setattr("app.services.mission_control.runtime_startup_coordination._STARTUP_LOCK", lock)
    assert try_acquire_startup_lock(phase="test")
    st = build_startup_lock_status()
    assert st["runtime_startup_lock"]["holder_pid"] is not None
    release_startup_lock_if_owner()
    st2 = build_startup_lock_status()
    assert st2["runtime_startup_lock"]["holder_pid"] is None
