"""Pagination — follow next links up to max_pages (Phase 21)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class PaginationHandler:
    """Walk pagination using CSS selector for the next link."""

    def __init__(self, fetcher: Any, extractor: Any) -> None:
        self.fetcher = fetcher
        self.extractor = extractor

    def _find_next_url(self, html: str, current_url: str, selector: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one(selector)
        if not next_link or not next_link.get("href"):
            return None
        href = str(next_link["href"]).strip()
        next_url = urljoin(current_url, href)
        cur = current_url.rstrip("/")
        nxt = next_url.rstrip("/")
        if nxt == cur or next_url == current_url:
            return None
        return next_url

    async def scrape_paginated(
        self,
        start_url: str,
        next_selector: str = 'a[rel="next"]',
        max_pages: int | None = None,
        extract_func: Callable[[str, str], Any] | None = None,
        **fetch_kwargs: Any,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        cap = max_pages if max_pages is not None else int(
            getattr(settings, "nexa_scraping_max_pages", 10) or 10
        )
        cap = max(1, min(cap, 500))

        all_rows: list[dict[str, Any]] = []
        current_url: str | None = start_url
        page_count = 0

        while current_url and page_count < cap:
            logger.info("scraping page %s: %s", page_count + 1, current_url[:200])
            result = await self.fetcher.fetch(current_url, **fetch_kwargs)
            if not result.get("success"):
                logger.error("fetch failed %s: %s", current_url, result.get("error"))
                break

            html = result.get("html") or ""
            payload: Any = None
            if extract_func:
                payload = extract_func(html, current_url)
            all_rows.append(
                {
                    "url": current_url,
                    "page": page_count + 1,
                    "data": payload,
                }
            )

            nxt = self._find_next_url(html, current_url, next_selector)
            current_url = nxt
            page_count += 1

        logger.info("pagination done pages=%s records=%s", page_count, len(all_rows))
        return all_rows


__all__ = ["PaginationHandler"]
