# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded e2e — patch cold runtime truth hydration for all e2e tests."""

from __future__ import annotations

from typing import Any

import pytest


def _light_truth(_uid: str | None = None) -> dict[str, Any]:
    return {
        "hydration_progress": {
            "partial": False,
            "tiers_complete": ["critical", "operational"],
            "percent_estimate": 1.0,
        },
        "runtime_resilience": {"status": "healthy"},
        "runtime_performance_intelligence": {"operational_responsiveness_score": 0.9},
        "launch_ready": True,
        "release_candidate": True,
        "phase4_step17": True,
        "phase4_step18": True,
        "phase4_step19": True,
        "phase4_step23": True,
        "enterprise_runtime_consolidated": True,
        "runtime_supervision_verified": True,
        "installer_interaction_locked": True,
        "process_supervision_locked": True,
    }


@pytest.fixture(autouse=True)
def _patch_light_runtime_truth_for_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.mission_control.runtime_truth_cache.get_cached_runtime_truth",
        lambda uid, builder: _light_truth(uid),
    )
    monkeypatch.setattr(
        "app.services.mission_control.runtime_async_hydration.hydrate_progressive_truth",
        lambda **_: _light_truth(),
    )
    monkeypatch.setattr(
        "app.services.setup.branding_purge.scan_user_facing_branding",
        lambda **_: {"clean": True, "violations": [], "bounded": True},
    )
    monkeypatch.setattr(
        "app.services.setup.ui_branding_purge_final.scan_ui_branding_final",
        lambda **_: {"nexa_ui_violations": [], "bounded": True},
    )
