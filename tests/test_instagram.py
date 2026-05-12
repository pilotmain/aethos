# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 24 — Instagram Graph client (mocked HTTP)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.social.instagram import InstagramClient


def test_instagram_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_PAGE_ACCESS_TOKEN", raising=False)
    get_settings.cache_clear()
    c = InstagramClient()
    out = c.post_feed("hi", media_urls=["https://example.com/a.jpg"])
    assert out.get("ok") is False
    assert out.get("error") == "instagram_not_configured"
    get_settings.cache_clear()


def test_instagram_post_feed_single_image_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "1784")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    get_settings.cache_clear()

    calls: list[tuple[str, dict]] = []

    class _Resp:
        status_code = 200

        def json(self) -> dict:
            return {"id": "cont1"}

    class _Client:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def post(self, url: str, data: dict | None = None, json: dict | None = None) -> _Resp:
            calls.append((url, dict(data or {})))
            return _Resp()

        def get(self, url: str) -> _Resp:
            return _Resp()

    monkeypatch.setattr("app.services.social.instagram.httpx.Client", _Client)

    c = InstagramClient()
    out = c.post_feed("caption", media_urls=["https://cdn.example.com/x.jpg"])
    assert out.get("ok") is True
    assert any("media_publish" in x[0] for x in calls)
    get_settings.cache_clear()
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
