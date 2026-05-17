# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_ownership_lock import (
    build_runtime_ownership_status,
    ownership_lock_path,
    release_runtime_ownership_if_owner,
    try_acquire_runtime_ownership,
)


def test_runtime_ownership_acquire_and_release(tmp_path, monkeypatch) -> None:
    lock = tmp_path / "ownership.lock"
    monkeypatch.setattr("app.services.mission_control.runtime_ownership_lock._OWNERSHIP_FILE", lock)
    monkeypatch.setattr("app.services.mission_control.runtime_ownership_lock._LIFECYCLE_FILE", tmp_path / "lifecycle.json")
    assert try_acquire_runtime_ownership(role="cli", force=True)
    st = build_runtime_ownership_status()
    assert st["runtime_ownership"]["this_process_owns"] is True
    release_runtime_ownership_if_owner()
    assert not ownership_lock_path().exists() or not build_runtime_ownership_status()["runtime_ownership"]["this_process_owns"]
