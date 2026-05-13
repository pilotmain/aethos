# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Thin HTTP clients for deployment visibility (Vercel API + Railway CLI fallback)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

import httpx

_VERCEL_PROJECTS = "https://api.vercel.com/v9/projects"


class VercelClient:
    """List projects via the Vercel REST API (requires ``VERCEL_API_TOKEN``)."""

    @staticmethod
    def list_projects(api_token: str | None) -> dict[str, Any]:
        token = (api_token or "").strip()
        if not token:
            return {
                "error": "missing_token",
                "message": "Set VERCEL_API_TOKEN in `.env` to list projects via the API.",
            }
        try:
            r = httpx.get(
                _VERCEL_PROJECTS,
                headers={"Authorization": f"Bearer {token}"},
                timeout=45.0,
            )
        except httpx.HTTPError as exc:
            return {"error": "http_error", "message": str(exc)}
        if r.status_code != 200:
            return {
                "error": "api_error",
                "status": r.status_code,
                "message": (r.text or "")[:500],
            }
        try:
            data = r.json()
        except json.JSONDecodeError:
            return {"error": "bad_json", "message": r.text[:300]}
        projects = data.get("projects") or []
        rows: list[dict[str, Any]] = []
        for p in projects:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "")
            name = str(p.get("name") or "")
            updated = str(p.get("updatedAt") or p.get("updated_at") or "")
            rows.append({"id": pid, "name": name, "updated_at": updated})
        return {"projects": rows}


class RailwayClient:
    """Best-effort Railway project listing via CLI (GraphQL varies by account setup)."""

    @staticmethod
    def list_projects_json() -> dict[str, Any]:
        if not shutil.which("railway"):
            return {
                "error": "cli_missing",
                "message": "Install the Railway CLI and run `railway login`, or use the Railway dashboard.",
            }
        last_err = ""
        for argv in (
            ["railway", "list", "--json"],
            ["railway", "list", "-j"],
            ["railway", "list"],
        ):
            try:
                proc = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return {"error": "cli_failed", "message": str(exc)}
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            last_err = err or last_err
            if proc.returncode != 0:
                continue
            if "--json" in argv or "-j" in argv:
                try:
                    parsed = json.loads(out)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return {"projects": [_railway_normalize(x) for x in parsed if isinstance(x, dict)]}
                if isinstance(parsed, dict) and "projects" in parsed:
                    return parsed
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            rows: list[dict[str, Any]] = []
            for ln in lines[:40]:
                if ln.startswith("{") and ln.endswith("}"):
                    try:
                        rows.append(_railway_normalize(json.loads(ln)))
                        continue
                    except json.JSONDecodeError:
                        pass
                name = re.split(r"\s{2,}", ln, maxsplit=1)[0].strip()
                if name:
                    rows.append({"name": name, "id": "", "updated_at": ""})
            if rows:
                return {"projects": rows}
            return {"error": "cli_parse", "message": err or out or "empty output"}
        return {"error": "cli_failed", "message": last_err or "railway list failed"}


def _railway_normalize(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(obj.get("id") or obj.get("projectId") or ""),
        "name": str(obj.get("name") or obj.get("project") or "unknown"),
        "updated_at": str(obj.get("updatedAt") or obj.get("updated_at") or ""),
    }


def ensure_vercel_cli_on_path() -> dict[str, Any]:
    """Return ``{ok: True}`` when ``vercel`` is available (``npm install -g vercel`` otherwise)."""
    if shutil.which("vercel"):
        return {"ok": True, "message": "vercel on PATH"}
    return {
        "ok": False,
        "error": "cli_missing",
        "message": "Install the Vercel CLI: npm install -g vercel",
    }


def vercel_cli_whoami() -> dict[str, Any]:
    """Best-effort ``vercel whoami`` (OAuth / token login must be done out-of-band)."""
    if not shutil.which("vercel"):
        return ensure_vercel_cli_on_path()
    try:
        proc = subprocess.run(
            ["vercel", "whoami"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": "cli_failed", "message": str(exc)}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "not_logged_in",
            "message": err or out or "Run `vercel login` once on this machine.",
        }
    return {"ok": True, "user": out[:200]}


__all__ = ["RailwayClient", "VercelClient", "ensure_vercel_cli_on_path", "vercel_cli_whoami"]
