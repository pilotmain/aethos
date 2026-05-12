# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 23 — privacy gate on synthetic dev payloads."""

from __future__ import annotations

import pytest

from app.services.dev_runtime.privacy import PrivacyBlockedError, gate_outbound_dev_payload


def test_blocks_openai_style_key_in_payload(db_session) -> None:
    with pytest.raises(PrivacyBlockedError):
        gate_outbound_dev_payload(
            {"log": "error token sk-abcdefghijklmnopqrstuvwxyz1234567890abcd"},
            db=db_session,
            user_id="web_priv_u1",
        )


def test_redact_storage_does_not_raise() -> None:
    from app.services.dev_runtime.privacy import redact_output_for_storage

    t = redact_output_for_storage("key sk-abc1234567890abcdef")
    assert "sk-" not in t or "[REDACTED]" in t
