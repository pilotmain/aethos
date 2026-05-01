"""Audit / correlation event types for Cursor Cloud Agent runs."""

from __future__ import annotations

# Align with plan: cursor.run.*
CURSOR_RUN_CREATED = "cursor.run.created"
CURSOR_RUN_STARTED = "cursor.run.started"
CURSOR_RUN_COMPLETED = "cursor.run.completed"
CURSOR_RUN_FAILED = "cursor.run.failed"
