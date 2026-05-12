# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Stable audit event types for trust / dashboard (P1).

Do not rename values without a DB migration strategy — dashboards and exports key off ``event_type``.

New trust-shaped ``event_type`` strings must be defined here and referenced by name from call sites.
Run ``python scripts/verify_trust_audit_taxonomy.py`` (also exercised in tests) to catch inline literals.
"""

from __future__ import annotations

from typing import Final

# --- Permission lifecycle ---
ACCESS_PERMISSION_REQUESTED: Final[str] = "access.permission.requested"
ACCESS_PERMISSION_GRANTED: Final[str] = "access.permission.granted"
ACCESS_PERMISSION_DENIED: Final[str] = "access.permission.denied"
ACCESS_PERMISSION_REVOKED: Final[str] = "access.permission.revoked"
ACCESS_PERMISSION_USED: Final[str] = "access.permission.used"
ACCESS_PERMISSION_BYPASSED: Final[str] = "access.permission.bypassed"

# Host executor job allowed after grants + enforcement (distinct from Trust "used" after completion).
HOST_EXECUTION_ALLOWED: Final[str] = "host.execution.allowed"

# Policy / scope rejection at execution time (distinct from denying a pending request).
ACCESS_HOST_EXECUTOR_BLOCKED: Final[str] = "access.host_executor.blocked"

# --- Network egress ---
NETWORK_EXTERNAL_SEND_ALLOWED: Final[str] = "network.external_send.allowed"
NETWORK_EXTERNAL_SEND_BLOCKED: Final[str] = "network.external_send.blocked"

# --- Sensitive material heuristic (outbound body gate) ---
ACCESS_SENSITIVE_EGRESS_WARNING: Final[str] = "access.sensitive_egress.warning"

# --- Enforcement pipeline (optional DB rows when enabled) ---
SAFETY_ENFORCEMENT_PATH: Final[str] = "safety.enforcement.path"

# --- Telegram / surface (legacy value preserved) ---
ACCESS_SURFACE_DENIED_LEGACY: Final[str] = "access_denied"

# --- First-dashboard-slice subset (queries, docs, CI allowlists) ---
TRUST_DASHBOARD_CORE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        ACCESS_PERMISSION_USED,
        ACCESS_PERMISSION_DENIED,
        ACCESS_SENSITIVE_EGRESS_WARNING,
        SAFETY_ENFORCEMENT_PATH,
        NETWORK_EXTERNAL_SEND_ALLOWED,
        NETWORK_EXTERNAL_SEND_BLOCKED,
        ACCESS_HOST_EXECUTOR_BLOCKED,
        ACCESS_PERMISSION_REQUESTED,
        ACCESS_PERMISSION_GRANTED,
        ACCESS_PERMISSION_REVOKED,
        ACCESS_PERMISSION_BYPASSED,
        HOST_EXECUTION_ALLOWED,
    }
)

# UI bucketing — read model maps every row to exactly one of these (stable contract).
TRUST_UI_STATUS_ALLOWED: Final[str] = "allowed"
TRUST_UI_STATUS_BLOCKED: Final[str] = "blocked"
TRUST_UI_STATUS_WARNING: Final[str] = "warning"
