# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.telegram_ownership_ux import (
    build_telegram_ownership_status,
    format_telegram_lock_failure,
)


def test_telegram_ownership_messages() -> None:
    out = build_telegram_ownership_status()
    assert "telegram_ownership" in out
    assert "message" in out["telegram_ownership"]


def test_telegram_lock_failure_copy() -> None:
    msg = format_telegram_lock_failure()
    assert "aethos runtime services" in msg.lower()
