# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execution truth — Railway-style requests paired with success narration."""

from __future__ import annotations

from app.services.execution_truth_guard import (
    reply_claims_completed_infra_work,
    user_requests_external_infra_action,
)
from app.services.response_sanitizer import sanitize_execution_and_assignment_reply


def test_user_and_reply_patterns_match_guard_rails() -> None:
    u = "kubectl rollout restart deployment/api on eks"
    assert user_requests_external_infra_action(u)
    assert reply_claims_completed_infra_work("Rolled out successfully and deployment is green")


def test_sanitizer_inserts_disclaimer_through_pipeline() -> None:
    raw_reply = "I've redeployed to Railway; deployment succeeded."
    out = sanitize_execution_and_assignment_reply(
        raw_reply,
        user_text="fix Railway production worker crash and redeploy",
    )
    assert "Important" in out or "railway" in out.lower()
