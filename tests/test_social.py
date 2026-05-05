"""Phase 22 — social automation service + API."""

from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.social.orchestrator import SocialOrchestrator, SocialPlatform


def test_social_platform_enum() -> None:
    assert SocialPlatform.TWITTER.value == "twitter"


def test_orchestrator_respects_global_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_SOCIAL_ENABLED", "false")
    get_settings.cache_clear()
    orch = SocialOrchestrator()

    async def _run() -> dict:
        return await orch.post(SocialPlatform.TWITTER, "hello")

    out = asyncio.run(_run())
    assert out.get("ok") is False
    assert out.get("error") == "social_disabled"


def test_orchestrator_post_twitter_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_SOCIAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_TWITTER_ENABLED", "true")
    get_settings.cache_clear()

    def fake_post(self: object, text: str, reply_to: str | None = None) -> dict:
        _ = self
        return {"ok": True, "data": {"text": text, "reply_to": reply_to}}

    monkeypatch.setattr(
        "app.services.social.twitter.TwitterClient.post_tweet",
        fake_post,
    )
    orch = SocialOrchestrator()

    async def _run() -> dict:
        return await orch.post(SocialPlatform.TWITTER, "hi")

    out = asyncio.run(_run())
    assert out.get("ok") is True


def test_social_post_requires_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "tok")
    monkeypatch.setenv("NEXA_SOCIAL_ENABLED", "true")
    get_settings.cache_clear()
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as c:
            r = c.post(
                "/api/v1/social/post",
                json={"platform": "twitter", "content": "x"},
                headers={"Authorization": "Bearer wrong"},
            )
            assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_social_post_503_when_disabled(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "secret")
    monkeypatch.setenv("NEXA_SOCIAL_ENABLED", "false")
    get_settings.cache_clear()
    client, _uid = api_client
    r = client.post(
        "/api/v1/social/post",
        json={"platform": "twitter", "content": "hello"},
        headers={"Authorization": "Bearer secret"},
    )
    assert r.status_code == 503


def test_social_post_200_mocked(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "secret")
    monkeypatch.setenv("NEXA_SOCIAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_TWITTER_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_post(
        self: object,
        platform: SocialPlatform,
        content: str,
        media_urls: list[str] | None = None,
        reply_to: str | None = None,
    ) -> dict:
        _ = (self, media_urls, reply_to)
        assert platform == SocialPlatform.TWITTER
        return {"ok": True, "data": {"dry_run": content}}

    monkeypatch.setattr(SocialOrchestrator, "post", fake_post)

    client, _uid = api_client
    r = client.post(
        "/api/v1/social/post",
        json={"platform": "twitter", "content": "hello"},
        headers={"Authorization": "Bearer secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True


def test_twitter_client_missing_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TWITTER_API_KEY", raising=False)
    monkeypatch.delenv("TWITTER_ACCESS_TOKEN", raising=False)
    get_settings.cache_clear()
    from app.services.social.twitter import TwitterClient

    c = TwitterClient()
    out = c.post_tweet("hello")
    assert out.get("ok") is False
