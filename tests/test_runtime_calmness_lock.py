# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_calmness_lock import build_runtime_calmness_lock, calm_operator_message


def test_calm_operator_message() -> None:
    assert "needs attention" in calm_operator_message("The API failed to connect")


def test_runtime_calmness_lock() -> None:
    out = build_runtime_calmness_lock({"runtime_resilience": {"status": "degraded"}})
    assert out["runtime_calmness_lock"]["locked"] is True
    assert "partial readiness" in out["runtime_calmness_lock"]["calm_narrative"].lower() or "stabiliz" in out[
        "runtime_calmness_lock"
    ]["calm_narrative"].lower()
