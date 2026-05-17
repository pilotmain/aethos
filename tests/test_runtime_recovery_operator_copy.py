# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_orchestration import build_startup_recovery_copy


def test_recovery_copy_is_calm() -> None:
    text = build_startup_recovery_copy()
    assert "coordination issue" in text.lower()
    assert "traceback" not in text.lower()
    assert "uvicorn" not in text.lower()


def test_recovery_copy_suggests_operator_actions() -> None:
    text = build_startup_recovery_copy(issue="port already in use")
    assert "doctor" in text.lower() or "recover" in text.lower()
