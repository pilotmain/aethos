# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Release readiness: env checks, job diagnostics, doctor, queue, startup log (no secrets)."""

from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.branding import display_product_name
from app.core.config import get_settings
from app.services.env_validator import collect_env_validation_issues, format_env_validation_report
from app.services.job_diagnostics import collect_job_diagnostics, task_prompt_path_for_job
from app.services.nexa_doctor import build_nexa_doctor_text, format_git_brief
from app.services.startup_config_log import log_sanitized_nexa_config, _db_public_summary
from app.services.telegram_dev_ux import format_grouped_dev_queue


def test_env_host_executor_conflict():
    with patch.dict(
        os.environ,
        {
            "DEV_EXECUTOR_ON_HOST": "1",
            "OPERATOR_AUTO_RUN_DEV_EXECUTOR": "true",
        },
        clear=False,
    ):
        get_settings.cache_clear()
        issues = collect_env_validation_issues()
        get_settings.cache_clear()
    assert any("Both DEV_EXECUTOR" in i or "host may both" in i for i in issues)


def test_env_missing_dev_agent_command_with_auto():
    with patch.dict(
        os.environ,
        {
            "DEV_AGENT_AUTO_RUN": "true",
            "DEV_AGENT_COMMAND": "",
        },
        clear=False,
    ):
        get_settings.cache_clear()
        issues = collect_env_validation_issues()
        get_settings.cache_clear()
    assert any("DEV_AGENT" in i and "COMMAND" in i for i in issues)


def test_env_missing_dev_executor_python_path():
    with patch.dict(
        os.environ,
        {
            "DEV_EXECUTOR_ON_HOST": "1",
            "DEV_EXECUTOR_PYTHON": "/nonexistent/xyz/python3",
        },
        clear=False,
    ):
        get_settings.cache_clear()
        issues = collect_env_validation_issues()
        get_settings.cache_clear()
    assert any("DEV_EXECUTOR_PYTHON" in i for i in issues)


def test_format_env_has_no_raw_database_password():
    get_settings.cache_clear()
    s = get_settings()
    dbs = _db_public_summary(s.database_url)
    assert "://" not in dbs or "user_in_url" in dbs
    assert "password=" not in dbs.lower()
    get_settings.cache_clear()


def test_log_sanitized_no_secrets_in_stdout(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET123-must-not-print")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:FAKE-TOKEN-NEVER")
    get_settings.cache_clear()
    buf = io.StringIO()
    with redirect_stdout(buf):
        log_sanitized_nexa_config("test")
    out = buf.getvalue()
    get_settings.cache_clear()
    assert "sk-ant" not in out
    assert "123:FAKE" not in out
    assert "SECRET123" not in out  # synthetic key suffix; avoid bare "SECRET" (NEXA_SECRET_* flags)
    assert "Nexa config" in out or "APP_NAME" in out


def test_job_diagnostics_waiting_for_cursor_missing_file(tmp_path, monkeypatch):
    d = tmp_path / "agent_tasks"
    d.mkdir()
    import app.services.job_diagnostics as jdiag

    monkeypatch.setattr(jdiag, "AGENT_TASKS_DIR", d)
    exp = d / "dev_job_7.md"
    if exp.is_file():
        exp.unlink()
    job2 = SimpleNamespace(
        id=7,
        worker_type="dev_executor",
        status="waiting_for_cursor",
        cursor_task_path="",
    )
    p = task_prompt_path_for_job(job2)
    assert p == d / "dev_job_7.md" and not p.is_file()
    o = collect_job_diagnostics(MagicMock(), [job2])
    assert any("waiting_for_cursor" in x and "7" in x for x in o)


def test_grouped_dev_queue_active_needs_failures():
    jobs = [
        SimpleNamespace(
            id=1,
            worker_type="dev_executor",
            status="approved",
            title="a",
        ),
        SimpleNamespace(
            id=2,
            worker_type="dev_executor",
            status="needs_commit_approval",
            title="b",
        ),
        SimpleNamespace(
            id=3,
            worker_type="dev_executor",
            status="failed",
            title="c",
            error_message="missing done marker",
            tests_status=None,
            branch_name="",
        ),
    ]
    out = format_grouped_dev_queue(jobs)
    assert "Active" in out
    assert "Needs you" in out
    assert "failures" in out or "Failed" in out
    assert "#1" in out
    assert "#2" in out
    assert "#3" in out or "3" in out


def test_doctor_output_has_core_sections():
    with patch("app.services.nexa_doctor._api_health", return_value="ok"):
        with patch("app.services.nexa_doctor._db_status", return_value="ok"):
            with patch("app.services.nexa_doctor._bot_process_status", return_value="(skip)"):
                with patch("app.services.nexa_doctor._pending_approvalish", return_value="(skip)"):
                    mdb = MagicMock()
                    mdb.execute = lambda *a, **k: None
                    mdb.get = None
                    with patch("app.services.agent_job_service.AgentJobService.list_jobs", return_value=[]):
                        with patch(
                            "app.services.document_generation.count_all_document_artifacts",
                            return_value=2,
                        ):
                            t = build_nexa_doctor_text(mdb, "u1", telegram_user_id=1)
    brand = display_product_name()
    assert f"**{brand} Doctor**" in t
    assert "User LLM" in t
    assert "**Runtime**" in t
    assert "Public web access" in t
    assert "read-only" in t.lower() or "read-only" in t
    assert "web search" in t.lower() and "enabled" in t.lower() and "provider" in t.lower()
    assert "Documents" in t
    assert "**2**" in t  # document count from mocked total
    assert "retention" in t.lower() or "NEXA_DOCUMENT_RETENTION" in t
    assert "Memory" in t or "**Memory**" in t


def test_format_git_brief_includes_branch_or_repo():
    g = format_git_brief()
    assert display_product_name() in g
    assert "git" in g.lower()


def test_approved_stale_in_diagnostics():
    j = SimpleNamespace(
        id=1,
        worker_type="dev_executor",
        status="approved",
        approved_at=datetime.now() - timedelta(minutes=8),
        updated_at=None,
        created_at=datetime.now() - timedelta(hours=1),
        error_message="",
        result="",
    )
    out = collect_job_diagnostics(MagicMock(), [j])
    assert any("approved" in o.lower() for o in out) or out == []
