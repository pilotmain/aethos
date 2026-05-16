# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Setup health checks and validation (Phase 4 Step 4)."""

from __future__ import annotations

import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def run_setup_health_checks(
    *,
    repo_root: Path,
    api_base: str = "http://127.0.0.1:8010",
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    py_ok = sys.version_info >= (3, 9)
    checks.append({"name": "python", "ok": py_ok, "detail": f"{sys.version_info.major}.{sys.version_info.minor}"})

    git_ok = shutil.which("git") is not None
    checks.append({"name": "git", "ok": git_ok, "detail": "found" if git_ok else "missing"})

    venv_ok = (repo_root / ".venv").is_dir()
    checks.append({"name": "venv", "ok": venv_ok, "detail": str(repo_root / ".venv")})

    env_ok = (repo_root / ".env").is_file() or (Path.home() / ".aethos" / ".env").is_file()
    checks.append({"name": "env_file", "ok": env_ok, "detail": "present" if env_ok else "missing"})

    try:
        from app.core.paths import get_runtime_state_path

        rt_ok = get_runtime_state_path().parent.exists()
    except Exception:
        rt_ok = (Path.home() / ".aethos").is_dir()
    checks.append({"name": "runtime_dir", "ok": rt_ok, "detail": str(Path.home() / ".aethos")})

    api_ok = False
    api_detail = "offline"
    try:
        req = urllib.request.Request(f"{api_base.rstrip('/')}/api/v1/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            api_ok = resp.getcode() == 200
            api_detail = f"HTTP {resp.getcode()}"
    except urllib.error.HTTPError as exc:
        api_detail = f"HTTP {exc.code}"
    except Exception as exc:
        api_detail = str(exc)[:80]
    checks.append({"name": "api_health", "ok": api_ok, "detail": api_detail})

    mc_ok = False
    try:
        req = urllib.request.Request("http://127.0.0.1:3000", method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            mc_ok = resp.getcode() < 500
            mc_detail = f"HTTP {resp.getcode()}"
    except Exception as exc:
        mc_detail = str(exc)[:60]
    else:
        mc_detail = mc_detail if mc_ok else "offline"
    checks.append({"name": "mission_control", "ok": mc_ok, "detail": mc_detail})

    passed = sum(1 for c in checks if c.get("ok"))
    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "all_critical_ok": py_ok and venv_ok and env_ok,
    }
