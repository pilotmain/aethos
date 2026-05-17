# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_startup_orchestration import build_runtime_startup_orchestration


def test_runtime_startup_orchestration() -> None:
    blob = build_runtime_startup_orchestration({})
    assert blob["runtime_startup_orchestration"]["never_premature_ready"] is True
