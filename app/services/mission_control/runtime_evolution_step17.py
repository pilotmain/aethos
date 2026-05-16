# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 17 — installer interaction and startup reliability lock."""

from __future__ import annotations

from typing import Any

from app.services.setup.installer_interaction_lock import build_installer_interaction_lock


def apply_runtime_evolution_step17_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    truth.update(build_installer_interaction_lock())
    truth["phase4_step17"] = True
    truth["installer_interaction_locked"] = True
    return truth
