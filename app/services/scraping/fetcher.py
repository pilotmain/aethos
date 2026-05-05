"""Smart async web fetcher — retry, timeout, rate limit, UA rotation (Phase 21)."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.web_access import validate_public_url_strict

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
)


def _parse_user_agent_list(raw: str | None) -> list[str]:
    t = (raw or "").strip()
    if not t:
        return list(_DEFAULT_USER_AGENTS)
    if t.startswith("["):
        try:
            data = json.loads(t)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [p.strip() for p in t.split("||") if p.strip()]


class ScrapingFetcher:
    """Async HTTP fetch with retries, jittered rate limiting, and optional proxy."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._ua_pool = _parse_user_agent_list(
            getattr(self.settings, "nexa_scraping_user_agents", None) or ""
        )
        self._last_request_monotonic = 0.0
        self._rate_lock = asyncio.Lock()

    async def _wait_for_rate_limit(self) -> None:
        rpm = max(1, int(getattr(self.settings, "nexa_scraping_rate_limit_per_minute", 60) or 60))
        interval = 60.0 / float(rpm)
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_monotonic
            if elapsed < interval:
                wait = interval - elapsed + random.uniform(0.05, 0.35)
                await asyncio.sleep(wait)
            self._last_request_monotonic = time.monotonic()

    def _build_headers(self, custom: dict[str, str] | None) -> dict[str, str]:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if getattr(self.settings, "nexa_scraping_stealth_mode", True):
            if self._ua_pool:
                headers["User-Agent"] = random.choice(self._ua_pool)
        if custom:
            headers.update(custom)
        return headers

    async def fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        """
        GET ``url``. Returns
        ``{success, html?, status_code?, url?, headers?, error?}``.
        """
        s = self.settings
        if not getattr(s, "nexa_scraping_enabled", True):
            return {"success": False, "error": "scraping_disabled", "url": url}

        v_err = validate_public_url_strict(url)
        if v_err:
            return {"success": False, "error": v_err, "url": url}

        timeout_sec = float(timeout or getattr(s, "nexa_scraping_timeout_seconds", 30) or 30)
        proxy = (getattr(s, "nexa_scraping_proxy_url", None) or "").strip() or None

        last_exc: str | None = None
        for attempt in range(max(1, retries)):
            await self._wait_for_rate_limit()
            req_headers = self._build_headers(headers)
            try:
                async with httpx.AsyncClient(
                    proxy=proxy,
                    follow_redirects=True,
                    timeout=httpx.Timeout(timeout_sec),
                    limits=httpx.Limits(max_connections=10),
                ) as client:
                    resp = await client.get(url, headers=req_headers)
                    text = resp.text
                    return {
                        "success": True,
                        "html": text,
                        "status_code": int(resp.status_code),
                        "url": str(resp.url),
                        "headers": {k: v for k, v in resp.headers.items()},
                    }
            except httpx.TimeoutException:
                last_exc = "Timeout"
                logger.warning("scrape timeout %s attempt=%s", url[:120], attempt + 1)
            except httpx.RequestError as e:
                last_exc = str(e)[:500]
                logger.warning("scrape request error %s: %s", url[:120], last_exc)
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)
        return {"success": False, "error": last_exc or "fetch_failed", "url": url}

    async def fetch_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        result = await self.fetch(url, **kwargs)
        if not result.get("success"):
            return result
        try:
            result["data"] = json.loads(result["html"] or "")
            return result
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}", "url": url}


__all__ = ["ScrapingFetcher", "_parse_user_agent_list"]
