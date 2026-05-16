# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.privacy.pii_detection import detect_pii


def test_detect_email_and_sk() -> None:
    text = "Contact me at user@example.com and key sk-abcdefghijklmnopqrstuvwxyz0123456789AB"
    m = detect_pii(text)
    cats = {x.category for x in m}
    assert "email" in cats
    assert "api_key" in cats
    for x in m:
        assert 0 <= x.start < x.end <= len(text)
        assert x.redacted_preview
        assert "@" not in x.redacted_preview or x.category != "api_key"


def test_detect_ssn() -> None:
    text = "SSN 123-45-6789 end"
    m = detect_pii(text)
    assert any(x.category == "ssn" for x in m)


def test_detect_auth_header() -> None:
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    m = detect_pii(text)
    assert any(x.category == "auth_header" for x in m)
