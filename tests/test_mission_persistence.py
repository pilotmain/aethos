# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 6 — mission and task rows persist."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.nexa_next_runtime import NexaMission, NexaMissionTask
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def test_mission_and_tasks_saved(nexa_runtime_clean) -> None:
    text = """Researcher: find robotics mission db row here
Analyst: write forecast summary here"""
    gctx = GatewayContext.from_channel("u_mission", "web", {})
    out = NexaGateway().handle_message(gctx, text)
    assert out["status"] == "completed"
    mid = out["result"][0]["mission_id"]

    m = nexa_runtime_clean.get(NexaMission, mid)
    assert m is not None
    assert m.user_id == "u_mission"
    assert m.status == "completed"

    n_tasks = nexa_runtime_clean.scalar(
        select(func.count()).select_from(NexaMissionTask).where(NexaMissionTask.mission_id == mid)
    )
    assert n_tasks == 2
    rows = nexa_runtime_clean.scalars(
        select(NexaMissionTask).where(NexaMissionTask.mission_id == mid)
    ).all()
    assert all(r.status == "completed" for r in rows)
    assert all(r.output_json is not None for r in rows)
