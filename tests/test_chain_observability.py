# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Week 3: chain observability logs (no execution semantics changes)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.schemas.agent_job import AgentJobCreate
from app.services import host_executor
from app.services.agent_job_service import AgentJobService
from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl


class _BaseSettings:
    nexa_host_executor_enabled = True
    host_executor_work_root = ""
    host_executor_timeout_seconds = 120
    host_executor_max_file_bytes = 262_144
    nexa_host_executor_chain_enabled = True
    nexa_host_executor_chain_max_steps = 10
    nexa_host_executor_chain_allowed_actions = ""

    def __init__(self, root: Path) -> None:
        self.host_executor_work_root = str(root)


class _AllOnNl:
    nexa_host_executor_enabled = True
    nexa_host_executor_chain_enabled = True
    nexa_nl_to_chain_enabled = True


def test_chain_step_and_summary_logs(caplog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)
    s = _BaseSettings(tmp_path)
    with patch.object(host_executor, "get_settings", return_value=s):
        with caplog.at_level(logging.INFO, logger="app.services.host_executor"):
            host_executor.execute_payload(
                {
                    "host_action": "chain",
                    "actions": [
                        {"host_action": "file_write", "relative_path": "o.txt", "content": "z"},
                    ],
                }
            )
    step_recs = [r for r in caplog.records if getattr(r, "nexa_event", None) == "chain_step"]
    assert len(step_recs) == 1
    assert step_recs[0].host_action == "file_write"
    assert getattr(step_recs[0], "duration_ms", None) is not None
    assert step_recs[0].success is True
    summary = [r for r in caplog.records if getattr(r, "nexa_event", None) == "chain_summary"]
    assert len(summary) == 1
    assert summary[0].chain_exit_reason == "complete"
    assert summary[0].chain_success_count == 1


def test_nl_chain_inference_log(caplog) -> None:
    caplog.set_level(logging.INFO)
    with patch("app.services.host_executor_nl_chain.get_settings", return_value=_AllOnNl()):
        with caplog.at_level(logging.INFO, logger="app.services.host_executor_nl_chain"):
            try_infer_readme_push_chain_nl("add a README and push")
    ev = [r for r in caplog.records if getattr(r, "nexa_event", None) == "nl_chain_inferred"]
    assert len(ev) == 1
    assert ev[0].nl_chain_pattern == "readme_push_nl"


def test_chain_job_approve_logs_timing(caplog) -> None:
    ensure_schema()
    db = SessionLocal()
    caplog.set_level(logging.INFO)
    service = AgentJobService()
    try:
        job = service.create_job(
            db,
            "obs_chain_user",
            AgentJobCreate(
                kind="local_action",
                worker_type="local_tool",
                title="chain",
                instruction="x",
                command_type="host-executor",
                payload_json={
                    "host_action": "chain",
                    "actions": [
                        {"host_action": "file_write", "relative_path": "a.txt", "content": "1"},
                    ],
                },
                source="test",
            ),
        )
        assert job.status == "needs_approval"
        with caplog.at_level(logging.INFO, logger="app.services.agent_job_service"):
            service.decide(db, "obs_chain_user", job.id, "approve")
        approved_recs = [
            r for r in caplog.records if getattr(r, "nexa_event", None) == "chain_job_approved"
        ]
        assert len(approved_recs) == 1
        assert approved_recs[0].job_id == job.id
        assert approved_recs[0].chain_length == 1
        assert getattr(approved_recs[0], "approval_time_ms", None) is not None
    finally:
        db.close()
