# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator truth — no definitive deploy success without verification."""

from __future__ import annotations

from app.services.operator_runners.base import forbid_unverified_success_language


def test_forbid_unverified_softens_deploy_language_when_not_verified() -> None:
    body = "We deployed successfully to production."
    out = forbid_unverified_success_language(verified=False, body=body)
    assert "deployed successfully" in body.lower()
    assert "proof" in out.lower() or "diagnostic" in out.lower() or "verified" in out.lower()


def test_forbid_unverified_pass_through_when_verified() -> None:
    body = "deployed successfully"
    assert forbid_unverified_success_language(verified=True, body=body) == body
