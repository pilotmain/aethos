# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_cold_start_reliability import build_runtime_cold_start_reliability


def test_cold_start_operator_message() -> None:
    out = build_runtime_cold_start_reliability({"hydration_progress": {"partial": True}})
    msg = out["cold_start_reliability"]["operator_message"]
    assert "preparing enterprise runtime" in msg.lower()
    assert msg.lower() != "loading..."
