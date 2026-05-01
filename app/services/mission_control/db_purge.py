"""Mission Control — what is stored where, and optional SQL purge for one user.

The Mission Control dashboard slice (`build_mission_control_dashboard`) aggregates:

**Database (per ``user_id``)**

- ``agent_assignments`` — orchestration list + mission map (spawn groups, handles).
- ``agent_jobs`` — active work, failed/running jobs in attention queue.
- ``agent_organizations`` / ``agent_role_assignments`` — team/org strip.
- ``access_permissions`` (pending) — approval cards.
- ``user_agents`` — custom agents (also loaded via ``/custom-agents``).
- ``audit_logs`` — trust activity, gateway failures (time-windowed); large table.

**Filesystem (workspace / memory dirs)**

- ``reports/mission_control.md``, ``timeline.jsonl``, ``agent_status.json`` — cleared by
  ``clear_workspace_reports`` / reset.
- ``memory/mission_control_ui_state.json`` — dismissed attention ids (not in SQL).

Deleting only the SQLite file (e.g. ``overwhelm_reset.db``) wipes *everything* for all users
if that file is your ``DATABASE_URL``; use the API purge below to clear one Nexa user without
removing other tables/users.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.access_permission import AccessPermission
from app.models.agent_job import AgentJob
from app.models.agent_team import AgentAssignment, AgentOrganization, AgentRoleAssignment
from app.models.audit_log import AuditLog
from app.models.user_agent import UserAgent
from app.services.access_permissions import STATUS_PENDING
from app.services.agent_runtime.paths import memory_dir, mission_control_md_path
from app.services.mission_control.cleanup_actions import clear_workspace_reports
from app.services.mission_control.ui_state import clear_attention_dismissals

logger = logging.getLogger(__name__)


def _uid(user_id: str) -> str:
    return (user_id or "").strip()[:64]


def mission_control_data_inventory(db: Session, user_id: str) -> dict[str, Any]:
    """Row counts and file hints for debugging Mission Control for one user."""
    uid = _uid(user_id)
    mc_path = mission_control_md_path()
    ui_state = memory_dir() / "mission_control_ui_state.json"
    inv: dict[str, Any] = {
        "user_id": uid,
        "database_url_note": "Mission Control reads the same DATABASE_URL as the API (Postgres or SQLite file).",
        "tables": {},
        "files": {
            "mission_control_md": str(mc_path),
            "mission_control_md_exists": mc_path.is_file(),
            "mission_control_ui_state": str(ui_state),
            "mission_control_ui_state_exists": ui_state.is_file(),
        },
    }

    def _cnt(model: type, *filters: Any) -> int:
        q = select(func.count()).select_from(model.__table__)
        for f in filters:
            q = q.where(f)
        return int(db.scalar(q) or 0)

    inv["tables"]["agent_assignments"] = _cnt(AgentAssignment, AgentAssignment.user_id == uid)
    inv["tables"]["agent_jobs"] = _cnt(AgentJob, AgentJob.user_id == uid)
    inv["tables"]["agent_organizations"] = _cnt(AgentOrganization, AgentOrganization.user_id == uid)
    org_ids = list(
        db.scalars(select(AgentOrganization.id).where(AgentOrganization.user_id == uid)).all()
    )
    if org_ids:
        inv["tables"]["agent_role_assignments"] = _cnt(
            AgentRoleAssignment, AgentRoleAssignment.organization_id.in_(org_ids)
        )
    else:
        inv["tables"]["agent_role_assignments"] = 0
    inv["tables"]["access_permissions_pending"] = _cnt(
        AccessPermission,
        AccessPermission.owner_user_id == uid,
        AccessPermission.status == STATUS_PENDING,
    )
    inv["tables"]["user_agents"] = _cnt(UserAgent, UserAgent.owner_user_id == uid)
    inv["tables"]["audit_logs_total_for_user"] = _cnt(AuditLog, AuditLog.user_id == uid)
    return inv


def purge_mission_control_database_for_user(
    db: Session,
    user_id: str,
    *,
    include_audit_logs: bool = False,
    include_pending_permissions: bool = True,
    include_custom_agents: bool = True,
    clear_workspace_files: bool = True,
) -> dict[str, Any]:
    """
    Hard-delete Mission Control–related rows for one user.

    Order respects FKs (assignment parent links nulled first).
    """
    uid = _uid(user_id)
    logger.info("mission_control sql_purge start user_prefix=%s", uid[:20])
    deleted: dict[str, int] = {}

    # AgentAssignment may self-reference parent_assignment_id — break links first.
    r1 = db.execute(
        update(AgentAssignment)
        .where(AgentAssignment.user_id == uid)
        .values(parent_assignment_id=None)
    )
    deleted["assignments_parent_links_cleared"] = getattr(r1, "rowcount", -1) or 0

    r2 = db.execute(delete(AgentAssignment).where(AgentAssignment.user_id == uid))
    deleted["agent_assignments"] = int(getattr(r2, "rowcount", 0) or 0)

    r3 = db.execute(delete(AgentJob).where(AgentJob.user_id == uid))
    deleted["agent_jobs"] = int(getattr(r3, "rowcount", 0) or 0)

    org_ids = list(
        db.scalars(select(AgentOrganization.id).where(AgentOrganization.user_id == uid)).all()
    )
    if org_ids:
        r4 = db.execute(delete(AgentRoleAssignment).where(AgentRoleAssignment.organization_id.in_(org_ids)))
        deleted["agent_role_assignments"] = int(getattr(r4, "rowcount", 0) or 0)
    else:
        deleted["agent_role_assignments"] = 0

    r5 = db.execute(delete(AgentOrganization).where(AgentOrganization.user_id == uid))
    deleted["agent_organizations"] = int(getattr(r5, "rowcount", 0) or 0)

    if include_pending_permissions:
        r6 = db.execute(
            delete(AccessPermission).where(
                AccessPermission.owner_user_id == uid,
                AccessPermission.status == STATUS_PENDING,
            )
        )
        deleted["access_permissions_pending"] = int(getattr(r6, "rowcount", 0) or 0)
    else:
        deleted["access_permissions_pending"] = 0

    if include_custom_agents:
        r7 = db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        deleted["user_agents"] = int(getattr(r7, "rowcount", 0) or 0)
    else:
        deleted["user_agents"] = 0

    if include_audit_logs:
        r8 = db.execute(delete(AuditLog).where(AuditLog.user_id == uid))
        deleted["audit_logs"] = int(getattr(r8, "rowcount", 0) or 0)
    else:
        deleted["audit_logs"] = 0

    db.commit()

    clear_attention_dismissals(uid)

    reports: dict[str, Any] | None = None
    if clear_workspace_files:
        reports = clear_workspace_reports(db, user_id=uid)

    logger.info(
        "mission_control sql_purge done user_prefix=%s deleted_keys=%s",
        uid[:20],
        list(deleted.keys()),
    )
    return {
        "ok": True,
        "user_id": uid,
        "deleted": deleted,
        "reports_cleared": reports,
        "note": "Trust summary counts may still reflect cached aggregates until hours window expires; audit_logs skipped unless include_audit_logs=true.",
    }
