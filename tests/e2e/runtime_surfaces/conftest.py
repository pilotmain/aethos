# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded runtime surface e2e — avoid full cold truth hydration."""

from __future__ import annotations

from typing import Any

import pytest


def _light_truth(_uid: str | None = None) -> dict[str, Any]:
    return {
        "hydration_progress": {"partial": False, "tiers_complete": ["critical", "operational"], "percent_estimate": 1.0},
        "runtime_resilience": {"status": "healthy"},
        "runtime_performance_intelligence": {"operational_responsiveness_score": 0.9},
        "launch_ready": True,
        "release_candidate": True,
        "phase4_step17": True,
    }


@pytest.fixture(autouse=True)
def _patch_light_runtime_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent multi-minute build_runtime_truth during MC runtime API e2e."""

    def _cached(uid: str, builder: Any) -> dict[str, Any]:
        try:
            return builder(uid)
        except Exception:
            return _light_truth(uid)

    monkeypatch.setattr(
        "app.services.mission_control.runtime_truth_cache.get_cached_runtime_truth",
        lambda uid, builder: _light_truth(uid),
    )
