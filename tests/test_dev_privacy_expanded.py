# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 24 — expanded secret detectors on outbound dev payloads."""

from __future__ import annotations

import pytest

from app.services.dev_runtime.privacy import PrivacyBlockedError, gate_outbound_dev_payload


def test_blocks_github_fine_grained_pat(db_session) -> None:
    with pytest.raises(PrivacyBlockedError):
        gate_outbound_dev_payload(
            {"log": "token github_pat_" + "a" * 22},
            db=db_session,
            user_id="u_p24",
        )


def test_blocks_npm_token(db_session) -> None:
    with pytest.raises(PrivacyBlockedError):
        gate_outbound_dev_payload(
            {"out": "prefix npm_" + "a" * 36 + " suffix"},
            db=db_session,
            user_id="u_p24",
        )


def test_blocks_pem_private_key(db_session) -> None:
    with pytest.raises(PrivacyBlockedError):
        gate_outbound_dev_payload(
            {"k": "-----BEGIN PRIVATE KEY-----\nMIIE"},
            db=db_session,
            user_id="u_p24",
        )


def test_blocks_dotenv_assignment_shape(db_session) -> None:
    with pytest.raises(PrivacyBlockedError):
        gate_outbound_dev_payload(
            {"log": "DATABASE_PASSWORD=supersecretvaluehere"},
            db=db_session,
            user_id="u_p24",
        )
