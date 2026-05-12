# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Stable worker id for locks, heartbeats, and audit metadata."""

from __future__ import annotations

import os
import socket

WORKER_ID: str = (os.getenv("DEV_WORKER_ID") or "").strip() or f"{socket.gethostname()}:{os.getpid()}"


def get_worker_id() -> str:
    return WORKER_ID
