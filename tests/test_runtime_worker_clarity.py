# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth
from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view


def test_runtime_workers_view_shape() -> None:
    view = build_runtime_workers_view(None)
    assert "orchestrator" in view
    assert isinstance(view.get("workers"), list)
    for w in view.get("workers") or []:
        assert "role" in w
        assert "summary" in w
        assert "ownership_chain" in w


def test_truth_includes_runtime_workers() -> None:
    truth = build_runtime_truth(user_id=None)
    workers = truth.get("runtime_workers") or {}
    assert "orchestrator" in workers
