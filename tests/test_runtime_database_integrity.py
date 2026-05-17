# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_db_coordination import build_database_integrity


def test_database_integrity_keys() -> None:
    blob = build_database_integrity()
    assert blob["database_owner"]["phase"] == "phase4_step25"
    assert "database_contention_state" in blob
    assert "database_runtime_integrity" in blob
