# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_recovery_actions import confirm_takeover, execute_runtime_takeover


def test_takeover_requires_yes() -> None:
    ok, msg = confirm_takeover(yes=False)
    assert ok is False
    assert "--yes" in msg


def test_takeover_with_yes(tmp_path, monkeypatch) -> None:
    lock = tmp_path / "ownership.lock"
    monkeypatch.setattr("app.services.mission_control.runtime_ownership_lock._OWNERSHIP_FILE", lock)
    monkeypatch.setattr("app.services.mission_control.runtime_ownership_lock._LIFECYCLE_FILE", tmp_path / "lc.json")
    result = execute_runtime_takeover(port=8010, yes=True)
    assert result.get("ok") is True
