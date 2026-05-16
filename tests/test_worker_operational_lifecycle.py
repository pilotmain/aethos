# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.worker_operational_lifecycle import build_worker_operational_lifecycle


def test_worker_lifecycle() -> None:
    out = build_worker_operational_lifecycle({"runtime_workers": {"active_count": 6}})
    assert out["lifecycle_governance"]["orchestrator_owned"] is True
    assert out["worker_lifecycle_maturity"]["active_workers"] == 6
