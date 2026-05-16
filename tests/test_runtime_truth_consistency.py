# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth
from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth


def test_cached_truth_matches_builder() -> None:
    builder = lambda uid: build_runtime_truth(user_id=uid)
    a = get_cached_runtime_truth(None, builder)
    b = get_cached_runtime_truth(None, builder)
    assert a.get("runtime_health") == b.get("runtime_health")
