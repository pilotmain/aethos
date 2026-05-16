# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import Any

from app.providers.provider_cli import run_cli_argv
from app.providers.provider_detection import detect_cli_path
from app.providers.provider_projects import list_vercel_projects
from app.providers.provider_registry import get_provider_spec
from app.runtime.runtime_state import utc_now_iso


def probe_provider_session(provider_id: str, *, timeout_sec: float) -> dict[str, Any]:
    """
    Probe one provider's CLI install + auth (non-destructive).

    Never includes raw tokens — only booleans, counts, and redacted previews.
    """
    pid = (provider_id or "").strip().lower()
    spec = get_provider_spec(pid)
    out: dict[str, Any] = {
        "provider": pid,
        "cli_installed": False,
        "cli_path": None,
        "authenticated": False,
        "auth_source": "local_cli",
        "project_count": None,
        "last_checked_at": utc_now_iso(),
        "error": None,
        "cli_preview": None,
    }
    if not spec:
        out["error"] = "unknown_provider"
        return out
    cli_path = detect_cli_path(pid)
    if not cli_path:
        return out
    out["cli_installed"] = True
    out["cli_path"] = cli_path
    auth_argv = list(spec.get("auth_argv") or [])
    if not auth_argv:
        return out
    code, so, se = run_cli_argv(auth_argv, timeout_sec=timeout_sec)
    blob = (so or "") + "\n" + (se or "")
    from app.providers.provider_privacy import redact_cli_output

    out["cli_preview"] = redact_cli_output(blob, max_out=600)
    ok = code == 0 and "not logged" not in blob.lower() and "not authenticated" not in blob.lower()
    if pid == "github" and code == 0:
        ok = "Logged in" in blob or "logged in" in blob.lower()
    if pid == "netlify" and code == 0:
        ok = "Not logged in" not in blob and "not logged in" not in blob.lower()
    out["authenticated"] = bool(ok)
    if pid == "vercel" and out["authenticated"]:
        projects, perr = list_vercel_projects(timeout_sec=timeout_sec)
        if projects:
            out["project_count"] = len(projects)
            out["projects"] = projects[:200]
        elif perr:
            out["project_list_error"] = perr[:400]
    return out
