# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified enterprise setup doctor (Phase 4 Step 16)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_enterprise_setup_doctor(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    checks: list[dict[str, Any]] = []
    fixes: list[str] = []

    try:
        from aethos_cli.setup_health import run_setup_health_checks

        health = run_setup_health_checks(repo_root=root)
        for c in health.get("checks") or []:
            checks.append({"name": c.get("name"), "ok": c.get("ok"), "detail": c.get("detail"), "area": "setup"})
        if not health.get("all_critical_ok"):
            fixes.append("Run `aethos setup repair` for dependency and env issues")
    except Exception as exc:
        checks.append({"name": "setup_health", "ok": False, "detail": str(exc)[:120], "area": "setup"})

    try:
        from app.services.setup.setup_status import build_setup_status

        st = build_setup_status(repo_root=root)
        checks.append({"name": "setup_complete", "ok": st.get("complete"), "detail": f"{st.get('passed')}/{st.get('total')}", "area": "setup"})
        mc = st.get("mission_control_ready") or {}
        checks.append({"name": "mission_control_ready", "ok": mc.get("ready"), "detail": "MC endpoints", "area": "mission_control"})
    except Exception as exc:
        checks.append({"name": "setup_status", "ok": False, "detail": str(exc)[:120], "area": "setup"})

    try:
        from app.services.setup.mission_control_ready_state import build_mission_control_ready_state

        mc = build_mission_control_ready_state(repo_root=root)
        checks.append({"name": "mc_bootstrap", "ok": mc.get("ready"), "detail": "connection seed", "area": "bootstrap"})
        if not mc.get("ready"):
            fixes.append("Run `aethos connection repair` to re-seed Mission Control credentials")
    except Exception as exc:
        checks.append({"name": "mc_ready", "ok": False, "detail": str(exc)[:120], "area": "mission_control"})

    try:
        from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities

        caps = build_runtime_capabilities()
        checks.append(
            {
                "name": "runtime_compatibility",
                "ok": True,
                "detail": caps.get("mc_compatibility_version"),
                "area": "runtime",
            }
        )
    except Exception as exc:
        checks.append({"name": "runtime_capabilities", "ok": False, "detail": str(exc)[:120], "area": "runtime"})

    try:
        from app.services.mission_control.runtime_process_supervision import build_runtime_process_supervision

        sup = build_runtime_process_supervision()
        own = sup.get("runtime_ownership") or {}
        conflicts = (sup.get("runtime_process_supervision") or {}).get("conflicts") or []
        checks.append(
            {
                "name": "runtime_ownership",
                "ok": not conflicts,
                "detail": "; ".join(conflicts) if conflicts else "no process conflicts",
                "area": "runtime",
            }
        )
        checks.append(
            {
                "name": "sqlite_db_health",
                "ok": (sup.get("runtime_db_health") or {}).get("ok"),
                "detail": (sup.get("runtime_db_health") or {}).get("detail"),
                "area": "runtime",
            }
        )
        if conflicts:
            fixes.append("Run `aethos runtime takeover` or `aethos restart runtime` to resolve process conflicts")
        if own.get("duplicate_ownership_risk"):
            fixes.append("Stop duplicate Telegram pollers — use embedded API bot OR standalone bot only")
    except Exception as exc:
        checks.append({"name": "process_supervision", "ok": False, "detail": str(exc)[:120], "area": "runtime"})

    bootstrap_path = Path.home() / ".aethos" / "mc_browser_bootstrap.json"
    checks.append(
        {
            "name": "browser_bootstrap",
            "ok": bootstrap_path.is_file(),
            "detail": str(bootstrap_path) if bootstrap_path.is_file() else "missing — run setup",
            "area": "bootstrap",
        }
    )

    ok_count = sum(1 for c in checks if c.get("ok"))
    return {
        "enterprise_setup_doctor": {
            "healthy": ok_count >= max(3, len(checks) - 2),
            "checks": checks,
            "recommended_fixes": fixes[:8],
            "auto_fix_suggestions": [
                "aethos setup repair",
                "aethos connection repair",
                "aethos runtime bootstrap",
            ],
            "summary": f"{ok_count}/{len(checks)} checks passed",
            "phase": "phase4_step20",
            "bounded": True,
        }
    }
