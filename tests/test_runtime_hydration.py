# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_hydration import (
    get_cached_slice,
    get_hydration_metrics,
    hydrate_runtime_truth_incremental,
    invalidate_slice_cache,
)
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_incremental_truth_has_performance_keys() -> None:
    invalidate_slice_cache(None)
    truth = build_runtime_truth(user_id=None)
    assert "runtime_performance" in truth
    assert "hydration_metrics" in truth
    assert "operational_responsiveness" in truth
    assert "runtime_scalability" in truth


def test_slice_cache_hit_on_second_build() -> None:
    invalidate_slice_cache(None, "_pytest_slice")
    get_cached_slice("_pytest_slice", None, lambda: {"ok": True}, ttl_sec=60.0)
    before = int(get_hydration_metrics().get("slice_cache_hits") or 0)
    get_cached_slice("_pytest_slice", None, lambda: {"ok": False}, ttl_sec=60.0)
    after = int(get_hydration_metrics().get("slice_cache_hits") or 0)
    assert after >= before + 1
    invalidate_slice_cache(None, "_pytest_slice")


def test_hydrate_assembles_core_fields() -> None:
    truth = hydrate_runtime_truth_incremental(user_id=None)
    assert truth.get("runtime_health") is not None
    assert "runtime_workers" in truth or truth.get("office") is not None
