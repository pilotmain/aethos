# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_ownership_lock import format_runtime_ownership_summary


def test_runtime_ownership_summary_lines() -> None:
    text = format_runtime_ownership_summary()
    assert "Runtime owner:" in text
    assert "SQLite:" in text
    assert "Next:" in text
