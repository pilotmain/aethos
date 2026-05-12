# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.project import Project
from app.services.dev_job_payload import merge_dev_payload
from app.services.dev_tools.aider_connector import AiderConnector
from app.services.dev_tools.formatting import format_dev_tools
from app.services.dev_tools.ide_connectors import ManualConnector
from app.services.dev_tools.project_open import open_project_with_tool
from app.services.dev_tools.registry import CONNECTORS, get_dev_tool, list_dev_tools
from app.services.project_registry import get_project_by_key
from app.services.telegram_project_commands import set_project_dev_mode, set_project_dev_tool


def test_dev_tool_registry_keys() -> None:
    expected = {
        "aider",
        "cursor",
        "vscode",
        "intellij",
        "pycharm",
        "webstorm",
        "android_studio",
        "xcode",
        "manual",
    }
    assert set(CONNECTORS.keys()) == expected
    assert len(list_dev_tools()) == len(expected)
    assert isinstance(get_dev_tool("nope"), type(None))
    assert get_dev_tool("AIDER") is not None
    assert isinstance(AiderConnector(), AiderConnector)
    assert isinstance(ManualConnector(), ManualConnector)


def _session_with_project() -> tuple:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(
        bind=engine,
        tables=[Project.__table__],
    )
    db = Session()
    p = Project(
        key="tproj",
        display_name="T",
        repo_path="/tmp/nexa-does-not-exist-for-test",
        provider_key="local",
        default_environment="staging",
        services_json="[]",
        environments_json="[]",
        is_default=True,
        is_enabled=True,
        preferred_dev_tool="aider",
        dev_execution_mode="autonomous_cli",
    )
    db.add(p)
    db.commit()
    return db, engine


def test_set_project_dev_tool_and_mode() -> None:
    db, engine = _session_with_project()
    try:
        assert "vscode" in set_project_dev_tool(db, "tproj", "vscode")
        row = get_project_by_key(db, "tproj")
        assert row is not None
        assert row.preferred_dev_tool == "vscode"
        assert "ide_handoff" in set_project_dev_mode(db, "tproj", "ide_handoff")
        row2 = get_project_by_key(db, "tproj")
        assert row2 is not None
        assert row2.dev_execution_mode == "ide_handoff"
    finally:
        db.close()
        engine.dispose()


def test_format_dev_tools() -> None:
    out = format_dev_tools()
    assert "Nexa Dev tools" in out
    assert "`aider`" in out
    assert "set-tool" in out


def test_dev_open_rejects() -> None:
    db, engine = _session_with_project()
    try:
        assert "don’t know project" in open_project_with_tool(db, "missing")
        p = get_project_by_key(db, "tproj")
        assert p is not None
        p.repo_path = None
        db.add(p)
        db.commit()
        assert "repo path" in open_project_with_tool(db, "tproj").lower()
    finally:
        db.close()
        engine.dispose()


def test_dev_open_calls_connector() -> None:
    db, engine = _session_with_project()
    try:
        p = get_project_by_key(db, "tproj")
        assert p is not None
        with patch.object(Path, "exists", return_value=True):
            p.repo_path = "/tmp/ok"
            p.preferred_dev_tool = "manual"
            db.add(p)
            db.commit()
            out = open_project_with_tool(db, "tproj")
            assert "Manual" in out or "handoff" in out.lower()
    finally:
        db.close()
        engine.dispose()


def test_merge_dev_payload_includes_fields() -> None:
    db, engine = _session_with_project()
    try:
        m = merge_dev_payload({"x": 1}, db, "tproj")
        assert m.get("project_key") == "tproj"
        assert m.get("preferred_dev_tool")
        assert m.get("dev_execution_mode")
    finally:
        db.close()
        engine.dispose()


def test_set_mode_rejects_invalid() -> None:
    db, engine = _session_with_project()
    try:
        r = set_project_dev_mode(db, "tproj", "nope")
        assert "Unsupported" in r
    finally:
        db.close()
        engine.dispose()


@patch.dict("os.environ", {"DEV_AGENT_COMMAND": ""}, clear=False)
def test_ide_connectors_aider_is_available_uses_path() -> None:
    c = AiderConnector()
    with patch("app.services.dev_tools.aider_connector.shutil.which", return_value="/x/aider"):
        assert c.is_available() is True
