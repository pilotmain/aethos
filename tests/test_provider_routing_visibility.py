# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_provider_routing_summary


def test_routing_summary_keys() -> None:
    s = build_provider_routing_summary()
    assert "provider" in s
    assert "local_first" in s
    assert "privacy_mode" in s
    assert "reason" in s
