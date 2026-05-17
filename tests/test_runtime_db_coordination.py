# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_db_coordination import build_runtime_db_health, sqlite_retry


def test_sqlite_retry_succeeds() -> None:
    calls = {"n": 0}

    def fn() -> int:
        calls["n"] += 1
        return 1

    assert sqlite_retry(fn, max_attempts=2) == 1
    assert calls["n"] == 1


def test_runtime_db_health_shape() -> None:
    out = build_runtime_db_health()
    assert "runtime_db_health" in out
    assert "ok" in out["runtime_db_health"]
