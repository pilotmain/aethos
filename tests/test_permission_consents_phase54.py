# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.permissions.consents import (
    check_consent,
    grant_consent,
    request_consent,
    revoke_consent,
)


def test_consent_grant_and_check() -> None:
    r = request_consent(scope="tool", resource="github.read", grant_mode="session")
    grant_consent(r)
    assert check_consent(scope="tool", resource="github.read") is True


def test_consent_revoke() -> None:
    r = request_consent(scope="x", resource="y")
    grant_consent(r)
    assert revoke_consent(r.consent_id, reason="user") is not None
    assert check_consent(scope="x", resource="y") is False
