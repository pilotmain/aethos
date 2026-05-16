# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_metrics_cache import get_cached_metrics, invalidate_metrics_cache


def test_metrics_cache_hit() -> None:
    calls = {"n": 0}

    def builder(uid: str) -> dict:
        calls["n"] += 1
        return {"user": uid, "v": 1}

    invalidate_metrics_cache("u1")
    a = get_cached_metrics("u1", builder)
    b = get_cached_metrics("u1", builder)
    assert a == b
    assert calls["n"] == 1
