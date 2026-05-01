"""Reliability layer: locks, preflight, worker state, commit guards."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.agent_job import AgentJob
from app.repositories.agent_job_repo import AgentJobRepository
from app.services.dev_preflight import run_dev_preflight
from app.services.worker_state import (
    clear_worker_paused,
    is_worker_paused,
    set_worker_paused,
)


@pytest.fixture
def mem_db():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    sm = sessionmaker(bind=eng, class_=Session, future=True)
    s = sm()
    yield s
    s.close()


def test_preflight_runs_checks():
    p = run_dev_preflight()
    assert "ok" in p
    assert isinstance(p.get("checks"), list)
    assert len(p.get("checks", [])) >= 3


def test_acquire_lock_prevents_double_holder(mem_db: Session) -> None:
    from datetime import datetime, timedelta

    r = AgentJobRepository()
    j = AgentJob(
        user_id="u1",
        source="t",
        kind="dev_task",
        worker_type="dev_executor",
        title="t",
        instruction="i",
        status="approved",
    )
    mem_db.add(j)
    mem_db.commit()
    mem_db.refresh(j)
    assert r.acquire_job_lock(mem_db, j, "worker-a", ttl_seconds=600) is True
    j2 = r.get(mem_db, j.id)
    assert (j2.locked_by or "") == "worker-a"
    assert r.acquire_job_lock(mem_db, j, "worker-b", ttl_seconds=600) is False
    r.release_job_lock(mem_db, j2)
    j3 = r.get(mem_db, j.id)
    assert r.acquire_job_lock(mem_db, j3, "worker-b", ttl_seconds=600) is True


def test_pause_file_roundtrip(tmp_path, monkeypatch) -> None:
    from app.services import worker_state as ws

    monkeypatch.setattr(ws, "RUNTIME", tmp_path)
    monkeypatch.setattr(ws, "PAUSE_FLAG", tmp_path / "dev_worker_paused")
    if ws.PAUSE_FLAG.is_file():
        ws.PAUSE_FLAG.unlink()
    assert is_worker_paused() is False
    set_worker_paused()
    assert is_worker_paused() is True
    clear_worker_paused()
    assert is_worker_paused() is False


def test_heartbeat_includes_worker_id_in_json(tmp_path, monkeypatch) -> None:
    from app.services import worker_heartbeat as wh

    monkeypatch.setattr(wh, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(wh, "HEARTBEAT_PATH", tmp_path / "h.json")
    with patch("app.services.worker_identity.get_worker_id", return_value="test:1"):
        wh.write_heartbeat(current_job_id=2, current_stage="agent_running", active_jobs=1)
    d = json.loads((tmp_path / "h.json").read_text())
    assert d.get("worker_id") == "test:1"
    assert d.get("current_stage") == "agent_running"
