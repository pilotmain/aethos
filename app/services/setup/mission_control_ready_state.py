# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control ready-state validation (Phase 4 Step 11)."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.core.setup_creds_file import read_setup_creds_dict

MC_ENDPOINTS = (
    "/api/v1/health",
    "/api/v1/setup/status",
    "/api/v1/runtime/capabilities",
    "/api/v1/mission-control/onboarding",
)


def _env_or_creds() -> tuple[str, str, str]:
    creds = read_setup_creds_dict()
    api = (
        os.environ.get("AETHOS_API_URL")
        or os.environ.get("NEXA_API_BASE")
        or creds.get("api_base")
        or "http://127.0.0.1:8010"
    ).rstrip("/")
    uid = os.environ.get("AETHOS_USER_ID") or os.environ.get("TEST_X_USER_ID") or creds.get("user_id") or ""
    token = os.environ.get("AETHOS_API_BEARER") or os.environ.get("NEXA_WEB_API_TOKEN") or creds.get("bearer_token") or ""
    return api, uid, token


def _probe(url: str, *, headers: dict[str, str] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers=headers or {"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"ok": resp.getcode() == 200, "status": resp.getcode()}
    except urllib.error.HTTPError as exc:
        return {"ok": exc.code < 500, "status": exc.code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


def build_mission_control_ready_state(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    api, uid, token = _env_or_creds()
    headers: dict[str, str] = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if uid:
        headers["X-User-Id"] = uid

    endpoint_results: dict[str, Any] = {}
    for ep in MC_ENDPOINTS:
        endpoint_results[ep] = _probe(f"{api}{ep}", headers=headers if ep != "/api/v1/health" else None)

    web_env = root / "web" / ".env.local"
    checks = {
        "api_url": bool(api),
        "bearer_token": bool(token),
        "user_id": bool(uid),
        "web_env_local": web_env.is_file(),
        "cors_configured": bool(os.environ.get("NEXA_WEB_ORIGINS")),
    }
    health_ok = endpoint_results.get("/api/v1/health", {}).get("ok")
    mc_ok = endpoint_results.get("/api/v1/mission-control/onboarding", {}).get("ok") or endpoint_results.get(
        "/api/v1/runtime/capabilities", {}
    ).get("ok")
    ready = health_ok and checks["bearer_token"] and checks["user_id"] and (checks["web_env_local"] or not (root / "web").is_dir())
    return {
        "ready": ready,
        "mission_control_ready": mc_ok,
        "checks": checks,
        "endpoints": endpoint_results,
        "api_base": api,
        "repair_hint": "aethos connection repair" if not ready else None,
        "bounded": True,
    }
