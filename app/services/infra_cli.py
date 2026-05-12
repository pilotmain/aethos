# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Allowlisted Railway / Vercel CLI subprocess helpers for ops + Telegram.

Uses fixed argv only (no shell injection). Returns user-facing Markdown-ish strings.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Sequence

from app.services.infra.cli_env import cli_auth_env


def _run(argv: Sequence[str], *, timeout: int = 45) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=cli_auth_env(),
        )
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def railway_whoami() -> str:
    if not shutil.which("railway"):
        return "❌ **Railway CLI** not found. Install: `npm install -g @railway/cli`"
    code, out, err = _run(["railway", "whoami"])
    if code == 0 and out:
        return f"🚂 **Railway** logged in as:\n`{out}`"
    detail = err or out or "not logged in"
    return (
        f"❌ **Railway** auth check failed ({detail}).\n"
        "Use **`RAILWAY_TOKEN`** (or `RAILWAY_API_TOKEN`) in `.env`, or run `railway login` on the worker."
    )


def railway_projects() -> str:
    if not shutil.which("railway"):
        return "❌ **Railway CLI** not found. Install: `npm install -g @railway/cli`"
    last = ""
    for argv in (["railway", "list"], ["railway", "projects"]):
        code, out, err = _run(argv)
        last = err or out or last
        if code == 0:
            body = out or "(empty)"
            return f"📁 **Railway projects**\n\n```\n{body[:12000]}\n```"
    return f"❌ **Railway** could not list projects: {last or 'unknown error'}"


def vercel_whoami() -> str:
    if not shutil.which("vercel"):
        return "❌ **Vercel CLI** not found. Install: `npm install -g vercel`"
    code, out, err = _run(["vercel", "whoami"])
    if code == 0 and out:
        return f"▲ **Vercel** account:\n`{out}`"
    wcode, wout, werr = _run(["vercel", "teams", "ls"])
    if wcode == 0:
        return f"▲ **Vercel** (whoami unclear; teams):\n```\n{wout[:8000]}\n```"
    return (
        f"❌ **Vercel** login required ({err or out or werr}).\n"
        "Set **`VERCEL_TOKEN`** / **`VERCEL_API_TOKEN`** in `.env`, or run `vercel login` on the worker."
    )


def vercel_projects_list() -> str:
    if not shutil.which("vercel"):
        return "❌ **Vercel CLI** not found. Install: `npm install -g vercel`"
    candidates: list[list[str]] = [
        ["vercel", "project", "ls"],
        ["vercel", "projects", "ls"],
        ["vercel", "ls"],
    ]
    last_err = ""
    for argv in candidates:
        code, out, err = _run(argv)
        last_err = err or out or last_err
        if code == 0:
            body = (out or "").strip()
            if not body:
                return (
                    "📁 **Vercel projects:** _(empty output — set **VERCEL_TOKEN** or run `vercel login` on the worker)_"
                )
            return f"📁 **Vercel projects**\n\n```\n{body[:12000]}\n```"
    w = vercel_whoami()
    if w.startswith("❌"):
        return w
    return f"❌ **Vercel** project listing failed: {last_err[:1500]}"


__all__ = [
    "railway_projects",
    "railway_whoami",
    "vercel_projects_list",
    "vercel_whoami",
]
