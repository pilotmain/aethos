# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.providers.provider_privacy import redact_cli_output


def test_redact_cli_output_strips_email_like_content() -> None:
    raw = "Logged in as dev@example.com token abc"
    out = redact_cli_output(raw)
    assert "dev@example.com" not in out
    assert "[REDACTED" in out or "REDACTED" in out
