# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 20 — enterprise runtime consolidation and production launch certification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.mission_control.runtime_hydration_diagnostics import build_runtime_hydration_diagnostics
from app.services.mission_control.runtime_recovery_finalization import build_runtime_recovery_finalization
from app.services.setup.production_cut_certification import build_production_cut_certification


def apply_runtime_evolution_step20_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    cert = build_production_cut_certification(truth=truth, repo_root=Path.cwd())
    truth.update(cert)
    truth.update(build_runtime_hydration_diagnostics(truth))
    truth.update(build_runtime_recovery_finalization(truth))
    truth["phase4_step20"] = True
    truth["enterprise_runtime_consolidated"] = True
    truth["production_cut_certified"] = bool(
        (cert.get("production_cut_certification") or {}).get("production_cut_ready")
    )
    return truth
