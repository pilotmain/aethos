# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persistent runtime parity (OpenClaw-class): ``~/.aethos/aethos.json``, workspace, heartbeat."""

from __future__ import annotations

from app.runtime.runtime_state import (
    default_runtime_state,
    load_runtime_state,
    mark_gateway_stopped,
    save_runtime_state,
)
from app.runtime.runtime_workspace import ensure_runtime_workspace_layout

__all__ = [
    "default_runtime_state",
    "ensure_runtime_workspace_layout",
    "load_runtime_state",
    "mark_gateway_stopped",
    "save_runtime_state",
]
