# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight event hooks for deploy context (Phase 2 Step 4; extend as needed)."""

from __future__ import annotations

from typing import Any


def note_resolution_event(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a small dict suitable for appending to resolution history (caller persists if desired)."""
    return {"kind": kind, **payload}
