# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings


@pytest.fixture
def _fresh():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_nexa_memory_redacts_when_redact_mode(api_client, monkeypatch: pytest.MonkeyPatch, _fresh) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "redact")
    client, _uid = api_client
    body = {"kind": "note", "title": "t", "body": "reach a@b.co ok", "meta": {}}
    r = client.post("/api/v1/nexa-memory", json=body)
    assert r.status_code == 200
    entry = r.json().get("entry") or {}
    meta = entry.get("meta") or {}
    priv = meta.get("privacy") or {}
    assert priv.get("scanned") is True
    assert "email" in (priv.get("pii_categories") or [])
    assert priv.get("redacted") is True
