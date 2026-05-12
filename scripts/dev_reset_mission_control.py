#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Clear Mission Control–related state for one Nexa user (local development).

Uses the same SQL purge as ``POST /api/v1/mission-control/database/purge-sql`` when
``NEXA_MISSION_CONTROL_SQL_PURGE=true``.

Optional SQL (adjust user id), if you prefer raw SQLite:

.. code-block:: sql

    DELETE FROM agent_assignments WHERE user_id = 'dev_user';
    DELETE FROM agent_heartbeats WHERE user_id = 'dev_user';

Tables such as ``agent_events`` / ``agent_artifacts`` are not present in this codebase;
equivalent lifecycle data lives on ``agent_assignments`` (``output_json``) and audit logs.

Usage::

    python scripts/dev_reset_mission_control.py --user-id dev_user
    python scripts/dev_reset_mission_control.py --user-id dev_user --include-agents
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import delete


def main() -> int:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    os.environ.setdefault("NEXA_MISSION_CONTROL_SQL_PURGE", "true")

    from app.core.db import SessionLocal, ensure_schema
    from app.models.agent_heartbeat import AgentHeartbeat
    from app.services.mission_control.db_purge import purge_mission_control_database_for_user

    p = argparse.ArgumentParser(description="Hard-reset Mission Control dev state for one user.")
    p.add_argument("--user-id", required=True, help="Nexa web/app user id (matches X-User-Id).")
    p.add_argument(
        "--include-agents",
        action="store_true",
        help="Also delete custom agents (user_agents) for this user.",
    )
    args = p.parse_args()
    uid = (args.user_id or "").strip()[:64]
    if not uid:
        print("user-id required", file=sys.stderr)
        return 2

    ensure_schema()
    with SessionLocal() as db:
        db.execute(delete(AgentHeartbeat).where(AgentHeartbeat.user_id == uid))
        db.commit()

        out = purge_mission_control_database_for_user(
            db,
            uid,
            include_audit_logs=False,
            include_pending_permissions=True,
            include_custom_agents=bool(args.include_agents),
            clear_workspace_files=True,
        )
    print(out)
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
