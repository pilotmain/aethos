# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — Mission Control snapshot reflects execution truth (heartbeat ≠ verified)."""

from __future__ import annotations

import uuid

from app.models.nexa_next_runtime import NexaMission, NexaMissionTask
from app.services.mission_control.execution_state import (
    derive_mission_execution_state,
    derive_task_execution_state,
    task_execution_verified,
)
from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_task_execution_verified_false_for_heartbeat_ok() -> None:
    assert task_execution_verified({"type": "heartbeat", "ok": True}) is False


def test_derive_task_heartbeat_external_is_diagnostic_only() -> None:
    assert (
        derive_task_execution_state(
            {
                "status": "completed",
                "execution_verified": False,
                "is_external_execution": True,
                "requires_access": False,
            }
        )
        == "diagnostic_only"
    )


def test_derive_task_internal_completed_without_verification() -> None:
    assert (
        derive_task_execution_state(
            {
                "status": "completed",
                "execution_verified": False,
                "is_external_execution": False,
                "requires_access": False,
            }
        )
        == "completed_unverified"
    )


def test_derive_task_requires_access_wins() -> None:
    assert (
        derive_task_execution_state(
            {
                "status": "completed",
                "execution_verified": False,
                "is_external_execution": True,
                "requires_access": True,
            }
        )
        == "access_required"
    )


def test_derive_mission_verified_when_tasks_verified() -> None:
    m = {
        "status": "completed",
        "requires_access": False,
        "is_external_execution": True,
        "execution_verified": True,
    }
    ts = [{"execution_verified": True}]
    assert derive_mission_execution_state(m, ts) == "verified"


def test_snapshot_heartbeat_external_mission_diagnostic_only(
    db_session, nexa_runtime_clean, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.should_gate_external_execution",
        lambda *_a, **_k: False,
    )
    uid = f"truth_{uuid.uuid4().hex[:8]}"
    mid = f"m_{uuid.uuid4().hex[:10]}"
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="hosted",
            status="completed",
            input_text="fix deploy https://railway.app/example",
        )
    )
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="worker",
            role="Worker",
            task="t",
            status="completed",
            depends_on=[],
            output_json={"type": "heartbeat", "ok": True},
        )
    )
    db_session.commit()

    snap = build_execution_snapshot(db_session, user_id=uid)
    task = snap["tasks"][0]
    assert task["execution_verified"] is False
    assert task["execution_state"] == "diagnostic_only"
    mission = next(x for x in snap["missions"] if x["id"] == mid)
    assert mission.get("is_external_execution") is True
    assert mission["execution_verified"] is False
    assert mission["execution_state"] == "diagnostic_only"


def test_snapshot_internal_heartbeat_completed_unverified(
    db_session, nexa_runtime_clean, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.should_gate_external_execution",
        lambda *_a, **_k: False,
    )
    uid = f"truth_{uuid.uuid4().hex[:8]}"
    mid = f"m_{uuid.uuid4().hex[:10]}"
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="local",
            status="completed",
            input_text="hello local refactor",
        )
    )
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="alpha",
            role="A",
            task="t",
            status="completed",
            depends_on=[],
            output_json={"type": "heartbeat", "ok": True},
        )
    )
    db_session.commit()

    snap = build_execution_snapshot(db_session, user_id=uid)
    assert snap["tasks"][0]["execution_state"] == "completed_unverified"


def test_snapshot_access_gate_task_access_required(db_session, nexa_runtime_clean) -> None:
    """No dev workspace → should_gate_external_execution requires connect copy; tasks show access_required."""
    uid = f"truth_{uuid.uuid4().hex[:8]}"
    mid = f"m_{uuid.uuid4().hex[:10]}"
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="rail",
            status="completed",
            input_text="check railway logs https://railway.app/z",
        )
    )
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="ops",
            role="Ops",
            task="t",
            status="completed",
            depends_on=[],
            output_json={"type": "heartbeat", "ok": True},
        )
    )
    db_session.commit()

    snap = build_execution_snapshot(db_session, user_id=uid)
    task = snap["tasks"][0]
    mission = next(x for x in snap["missions"] if x["id"] == mid)
    assert mission.get("requires_access") is True
    assert task["execution_state"] == "access_required"
    assert mission["execution_state"] == "access_required"


def test_snapshot_verified_external_when_output_non_stub(db_session, nexa_runtime_clean, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.should_gate_external_execution",
        lambda *_a, **_k: False,
    )
    uid = f"truth_{uuid.uuid4().hex[:8]}"
    mid = f"m_{uuid.uuid4().hex[:10]}"
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="hosted",
            status="completed",
            input_text="fix deploy https://railway.app/example",
        )
    )
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="runner",
            role="Runner",
            task="t",
            status="completed",
            depends_on=[],
            output_json={"kind": "repair", "changed": True},
        )
    )
    db_session.commit()

    snap = build_execution_snapshot(db_session, user_id=uid)
    task = snap["tasks"][0]
    assert task["execution_verified"] is True
    assert task["execution_state"] == "verified"
    mission = next(x for x in snap["missions"] if x["id"] == mid)
    assert mission["execution_verified"] is True
    assert mission["execution_state"] == "verified"
