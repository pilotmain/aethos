# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight in-process counters for observability (Phase 11)."""

from __future__ import annotations

import threading
import time
from typing import Any

_BOOT_MONO = time.monotonic()
_BOOT_WALL = time.time()

_lock = threading.Lock()

_http_requests_total = 0
_provider_calls_total = 0
_provider_latency_ms_sum = 0.0
_provider_latency_count = 0
_privacy_blocks_total = 0
_missions_completed_total = 0
_missions_timeout_total = 0


def record_http_request() -> None:
    global _http_requests_total
    with _lock:
        _http_requests_total += 1


def record_provider_call(*, latency_ms: float) -> None:
    global _provider_calls_total, _provider_latency_ms_sum, _provider_latency_count
    with _lock:
        _provider_calls_total += 1
        _provider_latency_ms_sum += latency_ms
        _provider_latency_count += 1


def record_privacy_block() -> None:
    global _privacy_blocks_total
    with _lock:
        _privacy_blocks_total += 1


def record_mission_completed() -> None:
    global _missions_completed_total
    with _lock:
        _missions_completed_total += 1


def record_mission_timeout() -> None:
    global _missions_timeout_total
    with _lock:
        _missions_timeout_total += 1


def uptime_seconds() -> float:
    return time.monotonic() - _BOOT_MONO


def snapshot() -> dict[str, Any]:
    with _lock:
        avg_lat = (
            (_provider_latency_ms_sum / _provider_latency_count) if _provider_latency_count else 0.0
        )
        return {
            "http_requests_total": _http_requests_total,
            "provider_calls_total": _provider_calls_total,
            "provider_latency_avg_ms": round(avg_lat, 3),
            "privacy_blocks_total": _privacy_blocks_total,
            "missions_completed_total": _missions_completed_total,
            "missions_timeout_total": _missions_timeout_total,
            "uptime_seconds": round(uptime_seconds(), 3),
            "boot_wall_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_BOOT_WALL)),
        }


__all__ = [
    "record_http_request",
    "record_provider_call",
    "record_privacy_block",
    "record_mission_completed",
    "record_mission_timeout",
    "uptime_seconds",
    "snapshot",
]
