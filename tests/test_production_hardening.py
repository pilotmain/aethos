# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.production_hardening import verify_production_bounds
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_production_hardening_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    hard = truth.get("production_hardening") or {}
    assert "checks" in hard
    assert "payload_bounds" in (hard.get("checks") or {})


def test_bounds_shape() -> None:
    out = verify_production_bounds({})
    assert "resilient" in out
