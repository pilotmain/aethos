# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 10 — enterprise setup, identity, routing, restart discipline."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_first_run import build_mission_control_first_run
from app.services.mission_control.runtime_identity_lock import build_runtime_identity_lock
from app.services.mission_control.runtime_provider_routing import build_runtime_provider_routing
from app.services.mission_control.runtime_restart_manager import build_runtime_restarts


def apply_runtime_evolution_step10_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    routing = build_runtime_provider_routing(truth)
    truth.update(routing)

    restarts = build_runtime_restarts(truth)
    truth["runtime_restarts"] = restarts
    truth.update(restarts)

    identity = build_runtime_identity_lock(truth)
    truth.update(identity)

    first_run = build_mission_control_first_run(truth)
    truth.update(first_run)

    truth["phase4_step10"] = True
    return truth
