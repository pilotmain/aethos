# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 10 — per-policy PII handling (allow / redact / block)."""

from __future__ import annotations

import pytest

from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload


def test_redact_default_scrubs_email() -> None:
    out = prepare_external_payload({"task": "reach me at x@example.com please"})
    assert "redacted" in out


def test_block_policy_raises_on_email() -> None:
    with pytest.raises(PrivacyBlockedError, match="PII blocked"):
        prepare_external_payload({"task": "reach me at x@example.com please"}, pii_policy="block")


def test_allow_policy_passes_email_through() -> None:
    payload = {"task": "reach me at x@example.com please"}
    out = prepare_external_payload(payload, pii_policy="allow")
    assert out["task"] == payload["task"]
