"""Phase 21 — web scraping service + API."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.scraping import DataExtractor, PaginationHandler, ScrapingFetcher


def test_extractor_css_and_metadata() -> None:
    ex = DataExtractor()
    html = "<html><head><title>T</title></head><body><div class='x'>hello</div></body></html>"
    assert ex.extract_css(html, ".x") == ["hello"]
    meta = ex.extract_metadata(html)
    assert meta.get("title") == "T"


def test_extractor_xpath() -> None:
    ex = DataExtractor()
    html = "<html><body><span id='n'>42</span></body></html>"
    got = ex.extract_xpath(html, "//span[@id='n']/text()")
    assert "42" in "".join(got)


def test_pagination_find_next_url() -> None:
    fetcher = ScrapingFetcher()
    ext = DataExtractor()
    ph = PaginationHandler(fetcher, ext)
    html = '<html><body><a rel="next" href="/page/2">next</a></body></html>'
    nxt = ph._find_next_url(html, "https://example.com/foo", 'a[rel="next"]')
    assert nxt == "https://example.com/page/2"


def test_scrape_fetch_rejects_bad_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "expected-token")
    get_settings.cache_clear()
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as c:
            r = c.post(
                "/api/v1/scraping/fetch",
                json={"url": "https://example.com"},
                headers={"Authorization": "Bearer wrong"},
            )
            assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_scrape_fetch_503_when_disabled(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "secret-token")
    monkeypatch.setenv("NEXA_SCRAPING_ENABLED", "false")
    get_settings.cache_clear()
    client, _uid = api_client
    r = client.post(
        "/api/v1/scraping/fetch",
        json={"url": "https://example.com"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert r.status_code == 503


def test_scrape_fetch_200_mocked(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "secret-token")
    monkeypatch.setenv("NEXA_SCRAPING_ENABLED", "true")
    get_settings.cache_clear()

    async def _fake_fetch(self: ScrapingFetcher, url: str, **kwargs: object) -> dict:
        _ = kwargs
        return {
            "success": True,
            "html": "<html></html>",
            "status_code": 200,
            "url": url,
            "headers": {},
        }

    monkeypatch.setattr(ScrapingFetcher, "fetch", _fake_fetch)

    client, _uid = api_client
    r = client.post(
        "/api/v1/scraping/fetch",
        json={"url": "https://example.com"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("status_code") == 200


def test_scrape_extract_css_mocked(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "tok")
    monkeypatch.setenv("NEXA_SCRAPING_ENABLED", "true")
    get_settings.cache_clear()

    mock = AsyncMock(
        return_value={
            "success": True,
            "html": "<html><body><h1>Hi</h1></body></html>",
            "status_code": 200,
            "url": "https://example.com",
            "headers": {},
        }
    )
    monkeypatch.setattr(ScrapingFetcher, "fetch", mock)

    client, _uid = api_client
    r = client.post(
        "/api/v1/scraping/extract",
        json={
            "url": "https://example.com",
            "extract_type": "css",
            "css_selector": "h1",
        },
        headers={"Authorization": "Bearer tok"},
    )
    assert r.status_code == 200
    assert r.json().get("data") == ["Hi"]
