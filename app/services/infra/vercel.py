# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Vercel CLI helper — projects list / deploy (fixed argv only).

Set **`VERCEL_TOKEN`** or **`VERCEL_API_TOKEN`** for non-interactive use (no `vercel login`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from app.services.infra.cli_env import cli_auth_env


class VercelClient:
    """Thin synchronous wrapper around the Vercel CLI."""

    def list_projects_json(self, *, timeout_sec: int = 45) -> list[dict[str, Any]]:
        if not shutil.which("vercel"):
            return []
        env = cli_auth_env()
        for argv in (
            ["vercel", "project", "ls", "--output", "json"],
            ["vercel", "projects", "ls", "--output", "json"],
            ["vercel", "projects", "list", "--output", "json"],
        ):
            try:
                r = subprocess.run(
                    list(argv),
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    env=env,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if r.returncode != 0 or not (r.stdout or "").strip():
                continue
            try:
                data = json.loads(r.stdout)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                continue
        return []

    def deploy_prod(self, *, project: str | None = None, timeout_sec: int = 180) -> dict[str, Any]:
        if not shutil.which("vercel"):
            return {"success": False, "error": "Vercel CLI not found. Install: `npm install -g vercel`"}
        cmd = ["vercel", "deploy", "--prod", "--yes"]
        if project:
            cmd.extend(["--project", project.strip()])
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=cli_auth_env(),
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"vercel deploy timed out after {timeout_sec}s"}
        except OSError as exc:
            return {"success": False, "error": str(exc)}
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        ok = r.returncode == 0
        return {"success": ok, "output": out, "stderr": err, "error": err if not ok else ""}


_vercel: VercelClient | None = None


def get_vercel_client() -> VercelClient:
    global _vercel
    if _vercel is None:
        _vercel = VercelClient()
    return _vercel


__all__ = ["VercelClient", "get_vercel_client"]
