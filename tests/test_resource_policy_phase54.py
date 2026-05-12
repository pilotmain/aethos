# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.resource_policy import load_resource_policy, policy_dict


def test_resource_policy_loads() -> None:
    p = load_resource_policy()
    assert p.max_parallel_tasks is None or isinstance(p.max_parallel_tasks, int)
    d = policy_dict()
    assert "max_cpu_percent" in d
