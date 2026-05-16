# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_lifecycle import run_runtime_lifecycle_sweeps


def test_lifecycle_sweep_returns_counts() -> None:
    out = run_runtime_lifecycle_sweeps()
    assert "agents_expired" in out
    assert "repair_rows_removed" in out
