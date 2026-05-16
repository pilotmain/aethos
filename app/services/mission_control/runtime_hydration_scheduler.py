# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Hydration scheduling — batch metrics and defer redundant state writes (Phase 4 Step 6)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_cycle_active = False
_current_generation: str | None = None
_slice_build_times: dict[str, float] = {}
_pending_metrics: dict[str, Any] = {}


def begin_hydration_cycle() -> str:
    global _cycle_active, _current_generation, _slice_build_times, _pending_metrics
    _cycle_active = True
    _current_generation = uuid.uuid4().hex[:12]
    _slice_build_times = {}
    _pending_metrics = {"hydration_generation_id": _current_generation, "cycle_started_at": utc_now_iso()}
    return _current_generation


def end_hydration_cycle(*, duration_ms: float | None = None) -> dict[str, Any]:
    global _cycle_active, _current_generation, _slice_build_times, _pending_metrics
    summary = {
        "hydration_generation_id": _current_generation,
        "hydration_duration_ms": round(duration_ms or 0.0, 2),
        "slice_build_times": dict(_slice_build_times),
        "lazy_load_metrics": _pending_metrics.get("lazy_load_metrics") or {},
    }
    _pending_metrics.update(summary)
    _flush_pending_metrics()
    _cycle_active = False
    _current_generation = None
    _slice_build_times = {}
    return summary


def should_defer_state_write() -> bool:
    return _cycle_active


def record_slice_build_time(slice_name: str, duration_ms: float) -> None:
    if _cycle_active:
        _slice_build_times[slice_name] = round(duration_ms, 2)


def defer_metric(**fields: Any) -> None:
    if _cycle_active:
        _pending_metrics.update({k: v for k, v in fields.items() if v is not None})
        return
    from app.services.mission_control.runtime_hydration import record_hydration_metric

    record_hydration_metric(**fields)


def _flush_pending_metrics() -> None:
    if not _pending_metrics:
        return
    st = load_runtime_state()
    h = st.setdefault("hydration_metrics", {})
    if isinstance(h, dict):
        h.update(_pending_metrics)
        h["updated_at"] = utc_now_iso()
    st["hydration_metrics"] = h
    save_runtime_state(st)
    _pending_metrics.clear()


def timed_slice_build(slice_name: str, builder: Any) -> Any:
    t0 = time.monotonic()
    try:
        return builder()
    finally:
        record_slice_build_time(slice_name, (time.monotonic() - t0) * 1000.0)
