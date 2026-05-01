from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.project import Project
from app.services.dev_orchestrator.dev_job_planner import (
    create_planned_dev_job,
    extract_explicit_dev_tool_request,
    prepare_dev_job_plan,
)


@pytest.fixture()
def db_with_project(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(bind=engine, tables=[Project.__table__])
    db = Session()
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.local"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "i", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    p = Project(
        key="nexa",
        display_name="Nexa",
        repo_path=str(tmp_path.resolve()),
        provider_key="local",
        default_environment="staging",
        services_json="[]",
        environments_json='["local"]',
        is_default=True,
        is_enabled=True,
        preferred_dev_tool="aider",
        dev_execution_mode="autonomous_cli",
    )
    db.add(p)
    db.commit()
    yield db, str(tmp_path)
    db.close()
    engine.dispose()


def test_extract_explicit_tool() -> None:
    assert extract_explicit_dev_tool_request("ask cursor to fix readme") is None
    assert extract_explicit_dev_tool_request("fix readme use cursor") == "cursor"
    assert extract_explicit_dev_tool_request("work in vscode please") == "vscode"
    assert extract_explicit_dev_tool_request("please use aider") == "aider"


def test_prepare_dev_job_plan_has_execution_decision(db_with_project) -> None:
    db, _rp = db_with_project
    out = prepare_dev_job_plan(
        db,
        user_id="u1",
        task_text="add README note for Nexa",
        project_key="nexa",
        extra_base={"source_dev_command": "create-cursor-task"},
    )
    pl = out["payload"]
    assert pl.get("execution_decision", {}).get("mode")
    assert pl.get("execution_decision", {}).get("tool_key")
    assert pl.get("orchestrator") is True
    assert pl.get("source_dev_command") == "create-cursor-task"


def test_explicit_use_cursor_overrides(db_with_project) -> None:
    db, _rp = db_with_project
    out = prepare_dev_job_plan(
        db,
        user_id="u1",
        task_text="add note use cursor",
        project_key="nexa",
    )
    assert out["plan"]["decision"].tool_key == "cursor"
    assert out["plan"]["decision"].mode == "ide_handoff"


def test_create_planned_dev_job_calls_service(db_with_project) -> None:
    db, _rp = db_with_project
    mock_js = MagicMock()
    fake_job = SimpleNamespace(id=99, status="needs_approval", payload_json={})
    mock_js.create_dev_task_with_policy.return_value = (fake_job, {})

    out = create_planned_dev_job(
        db,
        user_id="u1",
        telegram_chat_id="123",
        task_text="docs tweak",
        project_key="nexa",
        source="telegram",
        job_service=mock_js,
    )
    assert out["job"].id == 99
    mock_js.create_dev_task_with_policy.assert_called_once()
    ac = mock_js.create_dev_task_with_policy.call_args[0][2]
    pl = dict(ac.payload_json or {})
    assert "execution_decision" in pl
