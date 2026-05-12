# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — Railway token / CLI availability on the worker."""

from __future__ import annotations

from app.services.external_execution_access import assess_external_execution_access


def test_railway_access_available_when_token_in_env(db_session, monkeypatch) -> None:
    monkeypatch.setenv("RAILWAY_TOKEN", "test-token-value")
    try:
        acc = assess_external_execution_access(db_session, "user-x")
        assert acc.railway_token_present is True
        assert acc.railway_access_available is True
    finally:
        monkeypatch.delenv("RAILWAY_TOKEN", raising=False)


def test_railway_access_available_when_api_token_alias(db_session, monkeypatch) -> None:
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    monkeypatch.setenv("RAILWAY_API_TOKEN", "api-token-value")
    try:
        acc = assess_external_execution_access(db_session, "user-y")
        assert acc.railway_token_present is True
        assert acc.railway_access_available is True
    finally:
        monkeypatch.delenv("RAILWAY_API_TOKEN", raising=False)
