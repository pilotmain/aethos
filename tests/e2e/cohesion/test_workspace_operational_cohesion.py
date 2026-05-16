# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_cohesion import derive_operational_views_from_truth
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_workspace_in_derived_views() -> None:
    views = derive_operational_views_from_truth({"workspace_intelligence": {"projects": []}})
    assert views.get("workspace_intelligence") is not None
