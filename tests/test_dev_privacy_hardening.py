# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 25 — gate agent context before external adapters."""

from __future__ import annotations

import pytest

from app.services.dev_runtime.privacy import PrivacyBlockedError, gate_agent_context_before_external


def test_local_stub_skips_strict_gate(db_session) -> None:
    ctx = {"diff": {"diff_preview": "binary diff chunk …"}}
    out = gate_agent_context_before_external(
        "local_stub",
        ctx,
        db=db_session,
        user_id="u_gate",
    )
    assert out["diff"]["diff_preview"]


def test_non_stub_blocks_secret_shaped_diff(db_session) -> None:
    with pytest.raises(PrivacyBlockedError):
        gate_agent_context_before_external(
            "aider",
            {"diff": {"diff_preview": "token sk-abcdefghijklmnopqrstuvwxyz1234567890abcd"}},
            db=db_session,
            user_id="u_gate",
        )
