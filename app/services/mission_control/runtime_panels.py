# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control live operational panels (Phase 2 Step 10)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_truth import build_runtime_panels_from_truth, build_runtime_truth


def build_runtime_panels(user_id: str | None) -> dict[str, Any]:
    truth = build_runtime_truth(user_id=user_id)
    return build_runtime_panels_from_truth(truth)
