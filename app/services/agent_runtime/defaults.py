# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Default tool manifest and seed JSON structures."""

from __future__ import annotations

DEFAULT_AGENT_TOOLS_MANIFEST: dict = {
    "version": "1.0",
    "tools": [
        {
            "name": "sessions_spawn",
            "description": "Spawn one or more governed agent sessions for a bounded task.",
            "enabled": True,
            "requires_permission": True,
            "audit_event": "agent_session.spawn_requested",
            "schema_ref": "sessions_spawn",
        },
        {
            "name": "background_heartbeat",
            "description": "Record heartbeat/progress state for an active agent or assignment.",
            "enabled": True,
            "requires_permission": False,
            "audit_event": "agent_session.heartbeat",
            "schema_ref": "background_heartbeat",
        },
    ],
}


def default_memory_json() -> dict:
    return {
        "version": "1.0",
        "workspace_id": "local",
        "organization_id": None,
        "spawn_groups": {},
        "assignments": {},
        "agents": {},
        "last_updated_at": None,
    }


def default_heartbeats_json() -> dict:
    return {"version": "1.0", "heartbeats": {}}


def default_mission_control_md() -> str:
    return (
        "# Mission Control Report\n\n"
        "## Active Agents\n\n"
        "| Agent | Assignment | Status | Last Heartbeat |\n"
        "|---|---:|---|---|\n"
        "| — | — | — | — |\n\n"
        "## Current Plan\n\n"
        "- (No spawn activity yet.)\n\n"
        "## Blockers\n\n"
        "None.\n\n"
        "## Last Updated\n\n"
        "(pending)\n"
    )


def default_agent_status_json() -> dict:
    return {"version": "1.0", "agents": {}, "last_updated_at": None}


def default_workspace_metadata(*, workspace_mode: str) -> dict:
    """Seed workspace_metadata.json from workspace mode (does not overwrite user edits)."""
    mode = (workspace_mode or "regulated").strip().lower()
    if mode == "developer":
        return {
            "version": "1.0",
            "workspace_id": "local",
            "workspace_mode": "developer",
            "domain_category": "unrestricted_dev",
            "regulated_domain": False,
            "approval_mode": "disabled_for_local_dev",
            "agent_template": "base_operator",
            "notes": "Local development mode. Use NEXA_APPROVALS_ENABLED=false only with "
            "NEXA_WORKSPACE_MODE=developer for bounded runtime tool testing.",
        }
    return {
        "version": "1.0",
        "workspace_id": "local",
        "workspace_mode": "regulated",
        "domain_category": "regulated",
        "regulated_domain": True,
        "approval_mode": "required",
        "agent_template": "regulated_assistant",
        "notes": "Regulated-default workspace posture.",
    }
