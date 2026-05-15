# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""In-process view of persisted runtime state (reads ``aethos.json``)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def get_runtime_snapshot() -> dict[str, Any]:
    """Return a copy of the canonical runtime JSON document."""
    return dict(load_runtime_state())
