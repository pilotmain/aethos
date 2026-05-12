# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 43 — scheduler dev missions route through :meth:`NexaGateway.handle_message`."""

from __future__ import annotations

import json
import uuid

from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.services.gateway.runtime import NexaGateway
from app.services.scheduler.dev_jobs import execute_dev_mission_job


def test_execute_dev_mission_job_invokes_gateway(monkeypatch, db_session) -> None:
    recorded: list[tuple[str, dict | None]] = []

    def fake_handle(self: NexaGateway, gctx, text: str, db=None):
        recorded.append((gctx.channel, gctx.extras.get("scheduled_dev_mission")))
        return {"mode": "chat", "text": "stub"}

    monkeypatch.setattr(NexaGateway, "handle_message", fake_handle)

    payload = {
        "type": "dev_mission",
        "workspace_id": "ws-dev",
        "goal": "probe",
        "preferred_agent": "local_stub",
    }
    row = NexaSchedulerJob(
        id=str(uuid.uuid4()),
        user_id="u_sched_gateway",
        label="t",
        mission_text=json.dumps(payload),
        kind="interval",
        interval_seconds=3600,
        enabled=True,
    )
    db_session.add(row)
    db_session.commit()

    assert execute_dev_mission_job(db_session, row) is True
    assert len(recorded) == 1
    assert recorded[0][0] == "scheduler"
    assert recorded[0][1] is not None
    assert recorded[0][1].get("workspace_id") == "ws-dev"


def test_structured_route_prefers_scheduled_payload_over_run_dev(monkeypatch, db_session) -> None:
    """Scheduled extras win before interactive ``run dev`` parsing."""
    from app.services.gateway.context import GatewayContext

    called: list[str] = []

    def fake_sched(gctx, text, db_inner):
        called.append("sched")
        return {"mode": "chat", "text": "from_scheduler"}

    monkeypatch.setattr("app.services.dev_runtime.run_dev_gateway.try_scheduled_dev_mission", fake_sched)

    gctx = GatewayContext.from_channel("u1", "scheduler", {"scheduled_dev_mission": {"workspace_id": "w"}})
    out = NexaGateway()._try_structured_route(gctx, "run dev: should not win", db_session)
    assert out is not None
    assert called == ["sched"]
