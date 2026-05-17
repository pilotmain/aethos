# SPDX-License-Identifier: Apache-2.0

from app.services.setup.setup_db_lock_handling import (
    format_calm_db_lock_message,
    is_database_locked_error,
    sanitize_setup_error,
)


def test_db_lock_calm_message() -> None:
    assert is_database_locked_error("sqlite3.OperationalError: database is locked")
    msg = format_calm_db_lock_message("database is locked")
    assert "active runtime" in msg
    assert "Traceback" not in msg


def test_sanitize_no_traceback() -> None:
    err = "Traceback (most recent call last):\n  File x\nOperationalError"
    out = sanitize_setup_error(err)
    assert "Traceback" not in out
