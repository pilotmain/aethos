# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Zero-conf operational continuity (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_SNAPSHOTS = 16


def _record_snapshot(truth: dict[str, Any]) -> None:
    from app.services.mission_control.runtime_hydration_scheduler import should_defer_state_write

    if should_defer_state_write():
        return
    st = load_runtime_state()
    snaps = st.setdefault("workspace_operational_snapshots", [])
    if isinstance(snaps, list):
        snaps.append(
            {
                "at": utc_now_iso(),
                "readiness": truth.get("runtime_readiness_score"),
                "pressure": (truth.get("operational_pressure") or {}).get("level"),
            }
        )
        if len(snaps) > _MAX_SNAPSHOTS:
            del snaps[: len(snaps) - _MAX_SNAPSHOTS]
        st["workspace_operational_snapshots"] = snaps
    save_runtime_state(st)


def build_runtime_resume_state(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    c = (truth or {}).get("operator_continuity") or {}
    return {
        "resume_available": c.get("resume_available") if isinstance(c, dict) else False,
        "last_context": c,
    }


def record_continuity_hydration_snapshot(truth: dict[str, Any] | None = None) -> None:
    """Persist one bounded workspace snapshot per hydration."""
    _record_snapshot(truth or {})


def build_workspace_operational_snapshots(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    st = load_runtime_state()
    snaps = st.get("workspace_operational_snapshots") or []
    return list(snaps)[-8:] if isinstance(snaps, list) else []


def build_continuity_recovery_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"score": 0.88 if (truth or {}).get("operator_continuity") else 0.7, "bounded": True}


def build_continuity_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"intact": True, "orchestrator_owned": True}


def build_operational_continuity_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "runtime_resume_state": build_runtime_resume_state(truth),
        "workspace_operational_snapshots": build_workspace_operational_snapshots(truth),
        "continuity_recovery_quality": build_continuity_recovery_quality(truth),
        "continuity_integrity": build_continuity_integrity(truth),
        "natural_recovery": True,
    }
