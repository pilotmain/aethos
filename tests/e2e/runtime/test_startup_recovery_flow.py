# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_orchestration import (
    build_operator_startup_actions,
    build_startup_recovery_copy,
)


def test_startup_recovery_flow_actions() -> None:
    actions = build_operator_startup_actions(recovering=True)
    assert "Retry" in actions
    assert "Repair runtime" in actions


def test_startup_recovery_flow_calm_headline() -> None:
    text = build_startup_recovery_copy(issue="database lock")
    assert "Attempting recovery" in text
