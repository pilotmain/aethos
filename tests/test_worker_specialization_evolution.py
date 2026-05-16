# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.worker_specialization_evolution import build_worker_adaptation_metrics


def test_worker_adaptation_orchestrator_owned() -> None:
    out = build_worker_adaptation_metrics({})
    assert out.get("orchestrator_owned") is True
    assert "worker_learning_state" in out
    assert "worker_specialization_confidence" in out
