# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_db_coordination import clear_db_lock_state, get_db_lock_state, sqlite_retry


def test_sqlite_lock_state_tracking() -> None:
    clear_db_lock_state()
    assert get_db_lock_state()["db_lock_waiting"] is False


def test_sqlite_retry_on_success() -> None:
    assert sqlite_retry(lambda: 42, max_attempts=2) == 42
