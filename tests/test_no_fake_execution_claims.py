# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execution truth — chat must not read as verified infra work without evidence."""

from __future__ import annotations

from app.services.execution_truth_guard import apply_execution_truth_disclaimer


def test_disclaimer_prepended_on_railway_style_success() -> None:
    user = "The Railway worker keeps crashing — please fix and redeploy the service"
    reply = "I've redeployed and the service is now healthy. Heartbeat returned ok."
    out = apply_execution_truth_disclaimer(user, reply, guard_enabled=True)
    assert "Important" in out
    assert "verified" in out.lower()
    assert reply in out
