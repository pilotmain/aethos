import logging
import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
if settings.database_url.startswith("sqlite"):
    _engine_kw: dict = {"connect_args": {"check_same_thread": False}, "future": True}
else:
    # Postgres / other servers: keep long-lived API healthy behind load balancers.
    _engine_kw = {"future": True, "pool_pre_ping": True}
engine = create_engine(settings.database_url, **_engine_kw)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session, future=True)


class Base(DeclarativeBase):
    pass


def _migrate_users_is_new_column() -> None:
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_new" in cols:
        return
    dialect = engine.dialect.name
    stmt = (
        "ALTER TABLE users ADD COLUMN is_new BOOLEAN NOT NULL DEFAULT TRUE"
        if dialect == "postgresql"
        else "ALTER TABLE users ADD COLUMN is_new BOOLEAN NOT NULL DEFAULT 1"
    )
    with engine.begin() as conn:
        conn.execute(text(stmt))


def _migrate_agent_jobs_telegram_and_result_file() -> None:
    insp = inspect(engine)
    if "agent_jobs" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("agent_jobs")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "telegram_chat_id" not in cols:
            t = "VARCHAR(64)" if dialect == "postgresql" else "VARCHAR(64)"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN telegram_chat_id {t} NULL"))
        if "result_file" not in cols:
            t = "VARCHAR(2000)" if dialect == "postgresql" else "VARCHAR(2000)"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN result_file {t} NULL"))


def _migrate_agent_jobs_hardening() -> None:
    insp = inspect(engine)
    if "agent_jobs" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("agent_jobs")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "risk_level" not in cols:
            t = "VARCHAR(32)" if dialect == "postgresql" else "VARCHAR(32)"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN risk_level {t} NULL"))
        if "tests_status" not in cols:
            t = "VARCHAR(32)" if dialect == "postgresql" else "VARCHAR(32)"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN tests_status {t} NULL"))
        if "tests_output" not in cols:
            tt = "TEXT" if dialect == "sqlite" else "TEXT"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN tests_output {tt} NULL"))
        if "override_failed_tests" not in cols:
            df = "BOOLEAN NOT NULL DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN NOT NULL DEFAULT 0"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN override_failed_tests {df}"))
        t2000 = "VARCHAR(2000)" if dialect == "postgresql" else "VARCHAR(2000)"
        t200 = "VARCHAR(200)" if dialect == "postgresql" else "VARCHAR(200)"
        t64i = "VARCHAR(64)" if dialect == "postgresql" else "VARCHAR(64)"
        t64d = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
        if "locked_by" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN locked_by {t200} NULL"))
        if "locked_at" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN locked_at {t64d} NULL"))
        if "lock_expires_at" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN lock_expires_at {t64d} NULL"))
        if "failure_stage" not in cols:
            tfs = "VARCHAR(64)" if dialect == "postgresql" else "VARCHAR(64)"
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN failure_stage {tfs} NULL"))
        if "failure_artifact_dir" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN failure_artifact_dir {t2000} NULL"))
        if "artifact_dir" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN artifact_dir {t2000} NULL"))
        if "approved_by_user_id" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN approved_by_user_id {t64i} NULL"))


def _migrate_users_v7_focus_and_interaction() -> None:
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "last_focus_task" not in cols:
            t = "TEXT" if dialect == "sqlite" else "VARCHAR(65535)"
            conn.execute(text(f"ALTER TABLE users ADD COLUMN last_focus_task {t}"))
        if "focus_attempts" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN focus_attempts INTEGER NOT NULL DEFAULT 0"))
        if "last_interaction_at" not in cols:
            dt = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
            conn.execute(text(f"ALTER TABLE users ADD COLUMN last_interaction_at {dt}"))


logger = logging.getLogger(__name__)


def _migrate_agent_key_overwhelm_reset_to_nexa() -> None:
    """Rename internal agent key overwhelm_reset -> nexa (Nexa product rebrand). Idempotent."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    table_names = set(insp.get_table_names())
    for t in ("agent_runs", "agent_heartbeats", "learning_events"):
        if t not in table_names:
            continue
        cols = {c["name"] for c in insp.get_columns(t)}
        if "agent_key" not in cols:
            continue
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE {t} SET agent_key = 'nexa' "
                    f"WHERE agent_key = 'overwhelm_reset'"
                )
            )
    if "agent_definitions" in table_names:
        with engine.begin() as conn:
            desc = "Your personal execution system — think clearly and get things done."
            has_nexa = conn.execute(
                text("SELECT 1 FROM agent_definitions WHERE key = 'nexa' LIMIT 1")
            ).first()
            has_old = conn.execute(
                text("SELECT 1 FROM agent_definitions WHERE key = 'overwhelm_reset' LIMIT 1")
            ).first()
            if has_old and has_nexa:
                # Both keys present (e.g. partial prior seed) — drop stale row, keep `nexa`.
                conn.execute(text("DELETE FROM agent_definitions WHERE key = 'overwhelm_reset'"))
            elif has_old:
                conn.execute(
                    text(
                        "UPDATE agent_definitions SET key = 'nexa', display_name = 'Nexa', "
                        "description = :d "
                        "WHERE key = 'overwhelm_reset'"
                    ),
                    {"d": desc},
                )


def _sync_agent_definitions_safe() -> None:
    from app.services.agent_db_seed import sync_agent_definitions

    db = SessionLocal()
    try:
        sync_agent_definitions(db)
    except Exception as exc:
        logger.warning("agent_definitions seed skipped: %s", exc)
    finally:
        db.close()


def _migrate_conversation_context_topic_authority() -> None:
    """Add topic authority fields (vNext). Idempotent for SQLite and PostgreSQL."""
    insp = inspect(engine)
    if "conversation_contexts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversation_contexts")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "active_topic_confidence" not in cols:
            t = "REAL" if dialect == "sqlite" else "DOUBLE PRECISION"
            conn.execute(
                text(f"ALTER TABLE conversation_contexts ADD COLUMN active_topic_confidence {t} NOT NULL DEFAULT 0.5")
            )
        if "last_topic_update_at" not in cols:
            dt = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
            conn.execute(text(f"ALTER TABLE conversation_contexts ADD COLUMN last_topic_update_at {dt} NULL"))
        if "manual_topic_override" not in cols:
            if dialect == "postgresql":
                conn.execute(
                    text("ALTER TABLE conversation_contexts ADD COLUMN manual_topic_override BOOLEAN NOT NULL DEFAULT FALSE")
                )
            else:
                conn.execute(
                    text("ALTER TABLE conversation_contexts ADD COLUMN manual_topic_override BOOLEAN NOT NULL DEFAULT 0")
                )


def _seed_default_project() -> None:
    """Idempotent: ensure at least one Project row; seed `nexa` as default if table is empty."""
    from app.models.project import Project
    from app.services.handoff_paths import PROJECT_ROOT

    with SessionLocal() as s:
        n = s.scalar(select(func.count()).select_from(Project))
        if n and n > 0:
            return
        provider = (os.environ.get("NEXA_OPS_PROVIDER", "local") or "local").strip().lower()
        if provider in ("", "docker"):
            provider = "local"
        default_env = (os.environ.get("NEXA_DEFAULT_ENVIRONMENT", "staging") or "staging").strip()
        repo = str(Path(PROJECT_ROOT).resolve())
        s.add(
            Project(
                key="nexa",
                display_name="Nexa",
                repo_path=repo,
                provider_key=provider,
                default_environment=default_env,
                services_json='["api", "bot", "db", "worker"]',
                environments_json='["local", "staging", "production"]',
                is_default=True,
                is_enabled=True,
                preferred_dev_tool="aider",
                dev_execution_mode="autonomous_cli",
            )
        )
        s.commit()


def _migrate_conversation_context_pending_project() -> None:
    insp = inspect(engine)
    if "conversation_contexts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversation_contexts")}
    if "pending_project_json" in cols:
        return
    tt = "TEXT" if "sqlite" in str(engine.dialect) or engine.dialect.name == "sqlite" else "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE conversation_contexts ADD COLUMN pending_project_json {tt} NULL"))


def _migrate_conversation_context_last_decision() -> None:
    insp = inspect(engine)
    if "conversation_contexts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversation_contexts")}
    if "last_decision_json" in cols:
        return
    tt = "TEXT" if "sqlite" in str(engine.dialect) or engine.dialect.name == "sqlite" else "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE conversation_contexts ADD COLUMN last_decision_json {tt} NULL"))


def _migrate_conversation_context_suggested_actions() -> None:
    insp = inspect(engine)
    if "conversation_contexts" not in insp.get_table_names():
        return
    tt = "TEXT" if "sqlite" in str(engine.dialect) or engine.dialect.name == "sqlite" else "TEXT"
    for col, ddl in (
        ("last_suggested_actions_json", f"ALTER TABLE conversation_contexts ADD COLUMN last_suggested_actions_json {tt} NULL"),
        ("next_action_pending_inject_json", f"ALTER TABLE conversation_contexts ADD COLUMN next_action_pending_inject_json {tt} NULL"),
        ("last_injected_action_json", f"ALTER TABLE conversation_contexts ADD COLUMN last_injected_action_json {tt} NULL"),
        ("current_flow_state_json", f"ALTER TABLE conversation_contexts ADD COLUMN current_flow_state_json {tt} NULL"),
    ):
        cols = {c["name"] for c in insp.get_columns("conversation_contexts")}
        if col in cols:
            continue
        with engine.begin() as conn:
            conn.execute(text(ddl))
        insp = inspect(engine)


def _migrate_projects_idea_workflow() -> None:
    insp = inspect(engine)
    if "projects" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("projects")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "idea_summary" not in cols:
            tt = "TEXT" if dialect == "sqlite" else "TEXT"
            conn.execute(text(f"ALTER TABLE projects ADD COLUMN idea_summary {tt} NULL"))
        if "workflow_step_index" not in cols:
            d0 = "INTEGER NOT NULL DEFAULT 0" if dialect == "sqlite" else "INTEGER NOT NULL DEFAULT 0"
            conn.execute(text(f"ALTER TABLE projects ADD COLUMN workflow_step_index {d0}"))


def _migrate_projects_dev_tool_columns() -> None:
    """Add preferred_dev_tool, dev_execution_mode; backfill nexa defaults."""
    insp = inspect(engine)
    if "projects" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("projects")}
    with engine.begin() as conn:
        if "preferred_dev_tool" not in cols:
            conn.execute(
                text("ALTER TABLE projects ADD COLUMN preferred_dev_tool VARCHAR(100) NULL")
            )
        if "dev_execution_mode" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN dev_execution_mode "
                    "VARCHAR(100) NOT NULL DEFAULT 'autonomous_cli'"
                )
            )
        conn.execute(
            text(
                "UPDATE projects SET preferred_dev_tool = 'aider' "
                "WHERE key = 'nexa' AND (preferred_dev_tool IS NULL OR TRIM(COALESCE(preferred_dev_tool, '')) = '')"
            )
        )
        conn.execute(
            text(
                "UPDATE projects SET dev_execution_mode = 'autonomous_cli' "
                "WHERE key = 'nexa' AND (dev_execution_mode IS NULL OR TRIM(COALESCE(dev_execution_mode, '')) = '')"
            )
        )


def _migrate_conversation_context_session_multiplex() -> None:
    """
    Add session_id + web_chat_title: multiple chat threads per user (web) while
    keeping Telegram on session_id=default. Replaces UNIQUE(user_id) with
    UNIQUE(user_id, session_id). Idempotent.
    """
    from sqlalchemy import inspect  # re-local for clarity in nested scope

    insp = inspect(engine)
    if "conversation_contexts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversation_contexts")}
    dialect = engine.dialect.name

    if "session_id" not in cols:
        v = "VARCHAR(64) NOT NULL DEFAULT 'default'" if dialect != "sqlite" else "VARCHAR(64) NOT NULL DEFAULT 'default'"
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE conversation_contexts ADD COLUMN session_id {v}"))
        if dialect == "sqlite":
            with engine.begin() as conn:
                conn.execute(text("UPDATE conversation_contexts SET session_id = 'default'"))
    if "web_chat_title" not in cols:
        w = "VARCHAR(80) NULL" if dialect != "sqlite" else "VARCHAR(80) NULL"
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE conversation_contexts ADD COLUMN web_chat_title {w}"))

    insp2 = inspect(engine)
    if "conversation_contexts" not in insp2.get_table_names():
        return
    cols2 = {c["name"] for c in insp2.get_columns("conversation_contexts")}
    if "session_id" not in cols2:
        return

    with engine.begin() as conn:
        if dialect == "sqlite":
            rows = conn.execute(text("PRAGMA index_list('conversation_contexts')")).fetchall() or []
            for r in rows:
                if len(r) < 2:
                    continue
                idx_name, unique = r[1], r[2] if len(r) > 2 else 0
                if not unique or not idx_name:
                    continue
                origin = r[3] if len(r) > 3 else None
                if origin == "pk":
                    continue
                if str(idx_name) == "uq_cc_user_session":
                    continue
                try:
                    inf = conn.execute(text(f"PRAGMA index_info({repr(str(idx_name))})")).fetchall()  # noqa: S608
                except Exception:  # noqa: BLE001
                    inf = []
                colnames = [x[2] for x in inf] if inf else []
                if colnames == ["user_id"]:
                    try:
                        qn = str(idx_name).replace('"', '""')
                        conn.execute(text(f'DROP INDEX IF EXISTS "{qn}"'))  # noqa: S608
                    except Exception:  # noqa: BLE001
                        pass
        elif dialect == "postgresql":
            for uq in insp2.get_unique_constraints("conversation_contexts", schema=None) or []:
                col = uq.get("column_names") or []
                n = uq.get("name")
                if col == ["user_id"] and n:
                    try:
                        nq = str(n).replace('"', '""')
                        conn.execute(
                            text(
                                f'ALTER TABLE conversation_contexts DROP CONSTRAINT IF EXISTS "{nq}"'  # noqa: S608
                            )
                        )
                    except Exception:  # noqa: BLE001
                        pass
            # Unique INDEX on user_id (legacy) is not always listed as a table constraint.
            for idx in insp2.get_indexes("conversation_contexts") or []:
                if not idx.get("unique"):
                    continue
                icol = list(idx.get("column_names") or [])
                iname = idx.get("name")
                if icol == ["user_id"] and iname and str(iname) != "uq_cc_user_session":
                    try:
                        nq = str(iname).replace('"', '""')
                        conn.execute(text(f'DROP INDEX IF EXISTS "{nq}"'))  # noqa: S608
                    except Exception:  # noqa: BLE001
                        pass

    if dialect not in ("sqlite", "postgresql"):
        return
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_cc_user_session "
                    "ON conversation_contexts (user_id, session_id)"
                )
            )
        else:
            try:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cc_user_session "
                        "ON conversation_contexts (user_id, session_id)"
                    )
                )
            except Exception:  # noqa: BLE001
                pass

    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(
                text(
                    "UPDATE conversation_contexts SET web_chat_title = 'Main session' "
                    "WHERE (web_chat_title IS NULL OR TRIM(COALESCE(web_chat_title, '')) = '') "
                    "AND session_id = 'default'"
                )
            )
        else:
            conn.execute(
                text(
                    "UPDATE conversation_contexts SET web_chat_title = 'Main session' "
                    "WHERE (web_chat_title IS NULL OR TRIM(COALESCE(web_chat_title, '')) = '') "
                    "AND session_id = 'default'"
                )
            )


def _migrate_learning_event_status() -> None:
    """Add learning_events.status (pending|approved|rejected|applied)."""
    insp = inspect(engine)
    if "learning_events" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("learning_events")}
    if "status" in cols:
        return
    dialect = engine.dialect.name
    df = "VARCHAR(32) NOT NULL DEFAULT 'pending'" if dialect == "postgresql" else "VARCHAR(32) NOT NULL DEFAULT 'pending'"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE learning_events ADD COLUMN status {df}"))
        if dialect == "postgresql":
            conn.execute(
                text(
                    "UPDATE learning_events SET status = 'rejected' "
                    "WHERE applied = true AND approved = false"
                )
            )
            conn.execute(
                text(
                    "UPDATE learning_events SET status = 'applied' "
                    "WHERE applied = true AND approved = true"
                )
            )
        else:
            conn.execute(
                text(
                    "UPDATE learning_events SET status = 'rejected' "
                    "WHERE applied = 1 AND approved = 0"
                )
            )
            conn.execute(
                text("UPDATE learning_events SET status = 'applied' "
                     "WHERE applied = 1 AND approved = 1")
            )
        # Remaining rows keep default 'pending' (no applied / not yet decided)


def _migrate_conversation_context_blocked_host() -> None:
    """Add conversation_contexts.blocked_host_executor_json for permission-gate resume."""
    insp = inspect(engine)
    if "conversation_contexts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversation_contexts")}
    if "blocked_host_executor_json" in cols:
        return
    txt = "TEXT"
    with engine.begin() as conn:
        conn.execute(
            text(f"ALTER TABLE conversation_contexts ADD COLUMN blocked_host_executor_json {txt} NULL")
        )


def _migrate_nexa_workspace_projects() -> None:
    """Create nexa_workspace_projects + conversation_contexts.active_project_id."""
    insp = inspect(engine)
    tables = list(insp.get_table_names())
    dialect = engine.dialect.name
    int_t = "INTEGER"
    txt = "TEXT"
    if "nexa_workspace_projects" not in tables:
        with engine.begin() as conn:
            if dialect == "postgresql":
                conn.execute(
                    text(
                        f"""
                        CREATE TABLE nexa_workspace_projects (
                            id SERIAL PRIMARY KEY,
                            owner_user_id VARCHAR(64) NOT NULL,
                            name VARCHAR(256) NOT NULL,
                            path_normalized {txt} NOT NULL,
                            description {txt} NULL,
                            created_at TIMESTAMP NULL,
                            updated_at TIMESTAMP NULL,
                            CONSTRAINT uq_nexa_ws_proj_owner_path UNIQUE (owner_user_id, path_normalized)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX ix_nexa_ws_proj_owner ON nexa_workspace_projects (owner_user_id)"
                    )
                )
            else:
                conn.execute(
                    text(
                        f"""
                        CREATE TABLE nexa_workspace_projects (
                            id {int_t} PRIMARY KEY AUTOINCREMENT,
                            owner_user_id VARCHAR(64) NOT NULL,
                            name VARCHAR(256) NOT NULL,
                            path_normalized {txt} NOT NULL,
                            description {txt} NULL,
                            created_at DATETIME NULL,
                            updated_at DATETIME NULL,
                            CONSTRAINT uq_nexa_ws_proj_owner_path UNIQUE (owner_user_id, path_normalized)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX ix_nexa_ws_proj_owner ON nexa_workspace_projects (owner_user_id)"
                    )
                )
    insp_cc = inspect(engine)
    if "conversation_contexts" not in insp_cc.get_table_names():
        return
    cols = {c["name"] for c in insp_cc.get_columns("conversation_contexts")}
    if "active_project_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                f"ALTER TABLE conversation_contexts ADD COLUMN active_project_id {int_t} NULL "
                "REFERENCES nexa_workspace_projects(id) ON DELETE SET NULL"
            )
        )


def _migrate_users_governance() -> None:
    """Add users.organization_id and users.governance_role (Phase 13)."""
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    dialect = engine.dialect.name
    t64 = "VARCHAR(64)" if dialect == "postgresql" else "VARCHAR(64)"
    t32 = "VARCHAR(32)" if dialect == "postgresql" else "VARCHAR(32)"
    with engine.begin() as conn:
        if "organization_id" not in cols:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN organization_id {t64} NULL"))
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_org_id ON users (organization_id)"))
            except Exception:  # noqa: BLE001
                pass
        if "governance_role" not in cols:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN governance_role {t32} NULL"))


def _migrate_access_permissions_last_used() -> None:
    insp = inspect(engine)
    if "access_permissions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("access_permissions")}
    if "last_used_at" in cols:
        return
    dialect = engine.dialect.name
    dt = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE access_permissions ADD COLUMN last_used_at {dt} NULL"))


def _migrate_agent_organizations_governance_org() -> None:
    insp = inspect(engine)
    if "agent_organizations" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("agent_organizations")}
    if "governance_organization_id" in cols:
        return
    t64 = "VARCHAR(64)"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE agent_organizations ADD COLUMN governance_organization_id {t64} NULL"))
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_agent_organizations_governance_org_id "
                    "ON agent_organizations (governance_organization_id)"
                )
            )
        except Exception:  # noqa: BLE001
            pass


def _migrate_nexa_missions_input_text() -> None:
    insp = inspect(engine)
    if "nexa_missions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("nexa_missions")}
    if "input_text" in cols:
        return
    tt = "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE nexa_missions ADD COLUMN input_text {tt} NULL"))


def _migrate_nexa_tasks_timing() -> None:
    """Phase 13 — task-level latency for reliability metrics."""
    insp = inspect(engine)
    if "nexa_tasks" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("nexa_tasks")}
    dialect = engine.dialect.name
    dt = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME"
    fl = "DOUBLE PRECISION" if dialect == "postgresql" else "REAL"
    with engine.begin() as conn:
        if "started_at" not in cols:
            conn.execute(text(f"ALTER TABLE nexa_tasks ADD COLUMN started_at {dt} NULL"))
        if "duration_ms" not in cols:
            conn.execute(text(f"ALTER TABLE nexa_tasks ADD COLUMN duration_ms {fl} NULL"))


def _migrate_agent_jobs_phase38_approval_persistence() -> None:
    """Phase 38 — awaiting_approval + approval_context_json + approval_decision."""
    insp = inspect(engine)
    if "agent_jobs" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("agent_jobs")}
    dialect = engine.dialect.name
    jt = "JSONB" if dialect == "postgresql" else "TEXT"
    df_false = "BOOLEAN NOT NULL DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN NOT NULL DEFAULT 0"
    with engine.begin() as conn:
        if "awaiting_approval" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN awaiting_approval {df_false}"))
        if "approval_context_json" not in cols:
            conn.execute(text(f"ALTER TABLE agent_jobs ADD COLUMN approval_context_json {jt} NULL"))
        if "approval_decision" not in cols:
            conn.execute(text("ALTER TABLE agent_jobs ADD COLUMN approval_decision VARCHAR(64) NULL"))


def _migrate_nexa_long_running_phase44() -> None:
    """Phase 44 — autonomy metadata on long-running sessions."""
    insp = inspect(engine)
    if "nexa_long_running_sessions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("nexa_long_running_sessions")}
    dialect = engine.dialect.name
    df_false = "BOOLEAN NOT NULL DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN NOT NULL DEFAULT 0"
    with engine.begin() as conn:
        if "auto_generated" not in cols:
            conn.execute(text(f"ALTER TABLE nexa_long_running_sessions ADD COLUMN auto_generated {df_false}"))
        if "priority" not in cols:
            conn.execute(text("ALTER TABLE nexa_long_running_sessions ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"))
        if "origin" not in cols:
            t = "VARCHAR(64) NOT NULL DEFAULT 'user'" if dialect == "postgresql" else "VARCHAR(64) NOT NULL DEFAULT 'user'"
            conn.execute(text(f"ALTER TABLE nexa_long_running_sessions ADD COLUMN origin {t}"))


def _migrate_nexa_autonomous_goal_id() -> None:
    """Phase 47 — link spawned tasks to parent goal rows."""
    insp = inspect(engine)
    if "nexa_autonomous_tasks" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("nexa_autonomous_tasks")}
    with engine.begin() as conn:
        if "goal_id" not in cols:
            conn.execute(text("ALTER TABLE nexa_autonomous_tasks ADD COLUMN goal_id VARCHAR(64) NULL"))


def _migrate_nexa_dev_steps_phase25() -> None:
    """Phase 25 — iteration + structured JSON on dev steps."""
    insp = inspect(engine)
    if "nexa_dev_steps" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("nexa_dev_steps")}
    dialect = engine.dialect.name
    jt = "JSONB" if dialect == "postgresql" else "TEXT"
    with engine.begin() as conn:
        if "iteration" not in cols:
            conn.execute(text("ALTER TABLE nexa_dev_steps ADD COLUMN iteration INTEGER NULL"))
        if "adapter" not in cols:
            conn.execute(text("ALTER TABLE nexa_dev_steps ADD COLUMN adapter VARCHAR(64) NULL"))
        if "input_json" not in cols:
            conn.execute(text(f"ALTER TABLE nexa_dev_steps ADD COLUMN input_json {jt} NULL"))
        if "output_json" not in cols:
            conn.execute(text(f"ALTER TABLE nexa_dev_steps ADD COLUMN output_json {jt} NULL"))
        if "test_result" not in cols:
            conn.execute(text(f"ALTER TABLE nexa_dev_steps ADD COLUMN test_result {jt} NULL"))


def ensure_schema() -> None:
    import app.models  # noqa: F401 — register all models (incl. TaskPattern) on Base.metadata

    Base.metadata.create_all(bind=engine)
    _seed_default_project()
    _migrate_agent_key_overwhelm_reset_to_nexa()
    _sync_agent_definitions_safe()
    _migrate_users_is_new_column()
    _migrate_users_v7_focus_and_interaction()
    _migrate_agent_jobs_telegram_and_result_file()
    _migrate_agent_jobs_hardening()
    _migrate_conversation_context_topic_authority()
    _migrate_conversation_context_pending_project()
    _migrate_conversation_context_last_decision()
    _migrate_conversation_context_suggested_actions()
    _migrate_conversation_context_session_multiplex()
    _migrate_projects_idea_workflow()
    _migrate_projects_dev_tool_columns()
    _migrate_learning_event_status()
    _migrate_access_permissions_last_used()
    _migrate_users_governance()
    _migrate_agent_organizations_governance_org()
    _migrate_nexa_workspace_projects()
    _migrate_conversation_context_blocked_host()
    _migrate_nexa_missions_input_text()
    _migrate_nexa_tasks_timing()
    _migrate_nexa_dev_steps_phase25()
    _migrate_nexa_long_running_phase44()
    _migrate_nexa_autonomous_goal_id()
    _migrate_agent_jobs_phase38_approval_persistence()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
