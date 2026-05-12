# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 56 — Mission Control snapshot exposes dev run progress for Active Work."""

from __future__ import annotations

import uuid

from app.core.db import ensure_schema
from app.models.dev_runtime import NexaDevRun, NexaDevWorkspace
from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_dev_run_snapshot_includes_progress_and_summary(db_session) -> None:
    ensure_schema()
    uid = f"u_aw_{uuid.uuid4().hex[:10]}"
    ws = NexaDevWorkspace(
        id=f"w_{uuid.uuid4().hex[:8]}",
        user_id=uid,
        name="panel-test",
        repo_path="/tmp/nexa_mc_aw",
        status="ready",
    )
    db_session.add(ws)
    rid = f"run_{uuid.uuid4().hex[:10]}"
    run = NexaDevRun(
        id=rid,
        user_id=uid,
        workspace_id=ws.id,
        goal="stabilize pytest",
        status="running",
        result_json={
            "summary": "Analyzing failures…",
            "progress_messages": ["Starting investigation…", "Running tests…"],
            "adapter_used": "local_stub",
            "iterations": 1,
            "tests_passed": False,
        },
    )
    db_session.add(run)
    db_session.commit()

    snap = build_execution_snapshot(db_session, user_id=uid)
    row = next(r for r in snap["dev_runs"] if r["id"] == rid)
    assert row.get("summary") == "Analyzing failures…"
    assert row.get("progress_messages") == ["Starting investigation…", "Running tests…"]
