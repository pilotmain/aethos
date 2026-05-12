# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control V2 UI contract: ready-loop phrases + routing helpers stay stable for the web layer."""

from __future__ import annotations

from app.services.response_sanitizer import READY_LOOP_PHRASES


def test_ready_loop_phrases_cover_confirmation_leakage() -> None:
    combined = " ".join(READY_LOOP_PHRASES)
    assert "should i proceed" in combined
    assert "awaiting backend confirmation" in combined


def test_route_kind_ops_available_for_dashboard_hooks() -> None:
    from app.services.routing.authority import RouteKind

    assert RouteKind.OPS.value == "ops"
