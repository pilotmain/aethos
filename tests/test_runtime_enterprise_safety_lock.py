# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_enterprise_safety_lock import build_runtime_enterprise_safety_lock


def test_runtime_enterprise_safety_lock() -> None:
    blob = build_runtime_enterprise_safety_lock({})
    assert "enterprise_runtime_safe" in blob
    assert blob["runtime_enterprise_safety_lock"]["duplicate_runtime_activity_prevented"] is not None
