"""Operator supervisor: auto-approve of queued dev jobs (optional)."""

from app.core import config
from app.core.db import SessionLocal, ensure_schema
from app.schemas.agent_job import AgentJobCreate
from app.services.agent_job_service import AgentJobService
from app.workers import operator_supervisor as sup


def _settings_with(**overrides: object) -> object:
    s = config.Settings()
    for k, v in {
        "operator_auto_approve_queued_dev_jobs": False,
        "operator_auto_run_local_tools": False,
        "operator_auto_run_dev_executor": False,
        "operator_auto_approve_review": False,
        "operator_auto_approve_commit_safe": False,
        "operator_auto_approve_all_commits": False,
        "dev_executor_on_host": False,
        **overrides,
    }.items():
        setattr(s, k, v)
    return s


def test_auto_approve_dev_task_when_enabled(monkeypatch) -> None:
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    try:
        j = jobs.create_job(
            db,
            "op_auto_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="Do a thing",
                instruction="Change one file",
                source="test",
            ),
        )
        assert j.status == "needs_approval"

        monkeypatch.setattr(sup, "get_settings", lambda: _settings_with(operator_auto_approve_queued_dev_jobs=True))
        r = sup.process_supervisor_cycle()
        assert j.id in (r.get("auto_approved_dev") or [])

        db.expire_all()
        updated = jobs.get_job(db, "op_auto_user", j.id)
        assert updated is not None
        assert updated.status == "approved"
    finally:
        db.close()


def test_does_not_auto_approve_non_dev_kind(monkeypatch) -> None:
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    try:
        j = jobs.create_job(
            db,
            "op_local_user",
            AgentJobCreate(
                kind="local_action",
                worker_type="local_tool",
                title="run",
                instruction="x",
                command_type="run-tests",
                source="test",
            ),
        )
        assert j.status in ("queued", "needs_approval")
        st_before = j.status
        monkeypatch.setattr(sup, "get_settings", lambda: _settings_with(operator_auto_approve_queued_dev_jobs=True))
        r = sup.process_supervisor_cycle()
        assert (r.get("auto_approved_dev") or []) == []
        updated = jobs.get_job(db, "op_local_user", j.id)
        assert updated is not None
        assert updated.status == st_before
    finally:
        db.close()


def test_skips_in_container_dev_executor_when_host_flag_set(monkeypatch) -> None:
    """DEV_EXECUTOR_ON_HOST=1 means the Mac runs dev_agent_executor; API must not race it."""
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    calls: list[str] = []

    def _capture(path: str, extra_env=None) -> dict:
        calls.append(path)
        return {"returncode": 0, "stdout": "", "stderr": ""}

    try:
        j = jobs.create_job(
            db,
            "host_flag_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="pick me",
                instruction="x",
                source="test",
            ),
        )
        jobs.decide(db, "host_flag_user", j.id, "approve")
        assert j.status == "approved"

        monkeypatch.setattr(sup, "_run_script", _capture)
        monkeypatch.setattr(
            sup,
            "get_settings",
            lambda: _settings_with(
                operator_auto_run_dev_executor=True,
                dev_executor_on_host=True,
            ),
        )
        r = sup.process_supervisor_cycle()
        assert r.get("dev_executor") is None
        assert calls == []
    finally:
        db.close()


def test_auto_approve_all_commits_when_enabled(monkeypatch) -> None:
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    try:
        j = jobs.create_job(
            db,
            "op_commit_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="any title",
                instruction="x",
                source="test",
                approval_required=False,
            ),
        )
        jobs.mark_needs_commit_approval(
            db, j, "summary for commit step"
        )
        db.expire_all()
        j2 = jobs.get_job(db, "op_commit_user", j.id)
        assert j2 is not None
        assert j2.status == "needs_commit_approval"

        monkeypatch.setattr(
            sup,
            "get_settings",
            lambda: _settings_with(operator_auto_approve_all_commits=True),
        )
        r = sup.process_supervisor_cycle()
        assert j.id in (r.get("auto_committed") or [])

        db.expire_all()
        j3 = jobs.get_job(db, "op_commit_user", j.id)
        assert j3 is not None
        assert j3.status == "commit_approved"
    finally:
        db.close()
