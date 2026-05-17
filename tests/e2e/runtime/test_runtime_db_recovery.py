# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_db_coordination import ensure_schema_with_recovery


def test_runtime_db_recovery_schema() -> None:
    result = ensure_schema_with_recovery()
    assert "ok" in result
