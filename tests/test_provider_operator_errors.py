# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deploy_context.errors import ProviderAuthenticationError
from app.providers.actions.provider_logs import classify_cli_text


def test_operator_error_payload_shape() -> None:
    e = ProviderAuthenticationError("login", suggestions=["vercel login"])
    p = e.to_payload()
    assert p["error_class"] == "ProviderAuthenticationError"
    assert "vercel login" in p["suggestions"][0]


def test_classify_cli_auth_hint() -> None:
    assert classify_cli_text("Error: not logged in, run login") == "missing_provider_auth"
