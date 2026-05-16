# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from typing import Any

from app.providers.provider_cli import run_cli_argv
from app.providers.provider_privacy import redact_cli_output


def list_vercel_projects(*, timeout_sec: float) -> tuple[list[dict[str, Any]], str | None]:
    """
    Best-effort ``vercel project ls --json`` parse.

    Returns ``(projects, error)`` where each project dict has only non-secret fields.
    """
    code, out, err = run_cli_argv(["vercel", "project", "ls", "--json"], timeout_sec=timeout_sec)
    if code != 0:
        tail = redact_cli_output((err or out)[:2000], max_out=800)
        return [], tail or "vercel_project_ls_failed"
    try:
        data = json.loads(out or "null")
    except json.JSONDecodeError:
        return [], "vercel_project_ls_invalid_json"
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        iterable = data
    elif isinstance(data, dict) and isinstance(data.get("projects"), list):
        iterable = data["projects"]
    else:
        return [], None
    for item in iterable:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or item.get("projectId") or "").strip()
        name = str(item.get("name") or "").strip()
        if not name and not pid:
            continue
        rows.append(
            {
                "id": pid or None,
                "name": name or None,
                "accountId": str(item.get("accountId") or "").strip() or None,
            }
        )
    return rows, None
