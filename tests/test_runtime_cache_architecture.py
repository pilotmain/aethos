# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.core.config import get_settings
from app.services.mission_control.runtime_hydration import get_cached_slice, invalidate_slice_cache
from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth, invalidate_runtime_truth_cache
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_cache_ttl_from_settings() -> None:
    s = get_settings()
    assert float(getattr(s, "aethos_truth_cache_ttl_sec", 30)) >= 5.0
    assert float(getattr(s, "aethos_truth_slice_ttl_sec", 15)) >= 1.0


def test_full_truth_cache_reuses_entry() -> None:
    invalidate_runtime_truth_cache(None)
    invalidate_slice_cache(None)
    a = get_cached_runtime_truth(None, lambda uid: build_runtime_truth(user_id=uid))
    b = get_cached_runtime_truth(None, lambda uid: build_runtime_truth(user_id=uid))
    assert a.get("runtime_health") == b.get("runtime_health")


def test_slice_invalidation_clears_bucket() -> None:
    invalidate_slice_cache(None, "_pytest_slice_inv")
    data = get_cached_slice("_pytest_slice_inv", None, lambda: {"v": 1}, ttl_sec=120.0)
    assert data.get("v") == 1
    invalidate_slice_cache(None, "_pytest_slice_inv")
