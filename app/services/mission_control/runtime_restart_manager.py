# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified runtime restart discipline (Phase 4 Step 10)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_RESTART_HISTORY = 24
RESTART_ORDER = ("connection", "api", "web", "bot", "runtime")


def record_restart_event(target: str, *, ok: bool, detail: str = "") -> None:
    st = load_runtime_state()
    hist = st.setdefault("runtime_restart_history", [])
    if isinstance(hist, list):
        hist.append({"target": target, "ok": ok, "detail": detail[:200], "at": utc_now_iso()})
        if len(hist) > _MAX_RESTART_HISTORY:
            del hist[: len(hist) - _MAX_RESTART_HISTORY]
        st["runtime_restart_history"] = hist
    save_runtime_state(st)


def build_restart_diagnostics() -> dict[str, Any]:
    return {
        "dependency_order": list(RESTART_ORDER),
        "health_validation": ["api_health", "mission_control", "runtime_capabilities"],
        "recoverable": True,
    }


def build_restart_recovery_summary(hist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    entries = hist or []
    last = entries[-1] if entries else {}
    return {
        "last_restart": last,
        "recommendation": "Run aethos restart connection" if entries and not last.get("ok") else "No restart required",
    }


def build_runtime_restart_recommendations(truth: dict[str, Any] | None = None) -> list[str]:
    truth = truth or {}
    recs: list[str] = []
    if (truth.get("runtime_resilience") or {}).get("status") == "degraded":
        recs.append("Restart API after configuration changes.")
    if not truth.get("truth_integrity_score"):
        recs.append("Run aethos restart connection to refresh Mission Control link.")
    return recs[:4]


def build_runtime_restarts(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    hist = list(st.get("runtime_restart_history") or [])[-12:]
    return {
        "restart_history": hist,
        "restart_diagnostics": build_restart_diagnostics(),
        "restart_recovery_summary": build_restart_recovery_summary(hist),
        "restart_health": {"recent_ok": sum(1 for h in hist if h.get("ok")), "bounded": True},
        "runtime_restart_recommendations": build_runtime_restart_recommendations(truth),
    }
