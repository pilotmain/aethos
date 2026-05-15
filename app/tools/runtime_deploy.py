"""Deployment tool step (parity shell — records intent + stage metadata)."""

from __future__ import annotations

import time
from typing import Any


def run_deploy_step(*, stage: str | None = None, note: str | None = None) -> dict[str, Any]:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "tool": "deploy",
        "stage": stage or "apply",
        "note": note or "",
        "status": "recorded",
        "completed_at": ts,
    }
