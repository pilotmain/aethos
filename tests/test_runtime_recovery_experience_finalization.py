# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_recovery_experience_finalization import build_runtime_recovery_experience_finalization


def test_runtime_recovery_experience_finalization() -> None:
    blob = build_runtime_recovery_experience_finalization({})
    assert blob["runtime_recovery_experience_finalization"]["enterprise_grade"] is True
