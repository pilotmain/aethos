# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.worker_accountability import build_worker_accountability
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_worker_accountability_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("worker_accountability")
    assert truth.get("worker_governance")
    assert truth.get("worker_operational_quality")


def test_worker_accountability_shape() -> None:
    acc = build_worker_accountability({})
    assert "reliability" in acc
