# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Multi-session runtime registry (OpenClaw Phase 1 — JSON-backed)."""

from __future__ import annotations

from app.runtime.sessions.session_manager import ensure_session_for_operator
from app.runtime.sessions.session_registry import (
    attach_task,
    detach_task,
    get_session,
    list_sessions_for_user,
    upsert_session,
)

__all__ = [
    "attach_task",
    "detach_task",
    "ensure_session_for_operator",
    "get_session",
    "list_sessions_for_user",
    "upsert_session",
]
