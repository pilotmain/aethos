# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Structured provider action results (Phase 2 Step 4)."""

from __future__ import annotations

from typing import Any


def action_result(
    *,
    provider: str,
    action: str,
    success: bool,
    project: str | None = None,
    deployment_id: str | None = None,
    url: str | None = None,
    logs_available: bool = False,
    summary: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "provider": provider,
        "action": action,
        "success": success,
        "project": project,
        "deployment_id": deployment_id,
        "url": url,
        "logs_available": logs_available,
        "summary": summary,
    }
    if extra:
        out["extra"] = extra
    return out
