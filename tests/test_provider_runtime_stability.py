# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_provider_routing_summary


def test_routing_summary_stable_keys() -> None:
    s = build_provider_routing_summary()
    for key in ("provider", "model", "reason", "fallback_used", "local_first", "privacy_mode"):
        assert key in s
