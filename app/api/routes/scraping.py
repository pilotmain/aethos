# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 21 — web scraping API (Bearer ``NEXA_CRON_API_TOKEN``, same as cron / browser)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from app.core.auth import verify_cron_token
from app.core.config import get_settings
from app.services.scraping import DataExtractor, PaginationHandler, ScrapingFetcher

router = APIRouter(prefix="/scraping", tags=["scraping"])


def _require_scraping() -> None:
    if not get_settings().nexa_scraping_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ok": False, "code": "SCRAPING_DISABLED", "error": "Set NEXA_SCRAPING_ENABLED=true"},
        )


class FetchRequest(BaseModel):
    url: HttpUrl
    timeout: int | None = Field(default=None, ge=1, le=300)
    retries: int = Field(default=3, ge=1, le=8)


class ExtractRequest(BaseModel):
    url: HttpUrl
    css_selector: str | None = Field(default=None, max_length=4000)
    xpath: str | None = Field(default=None, max_length=4000)
    regex: str | None = Field(default=None, max_length=4000)
    extract_type: Literal["css", "xpath", "regex"] = "css"


class PaginatedRequest(BaseModel):
    start_url: HttpUrl
    next_selector: str = Field(default='a[rel="next"]', min_length=1, max_length=2000)
    max_pages: int | None = Field(default=None, ge=1, le=500)
    extract_css: str | None = Field(default=None, max_length=4000)


@router.post("/fetch")
async def api_fetch(
    request: FetchRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_scraping()
    fetcher = ScrapingFetcher()
    result = await fetcher.fetch(
        str(request.url),
        timeout=request.timeout,
        retries=request.retries,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(result.get("error") or "fetch failed"),
        )
    return {
        "ok": True,
        "html": result.get("html"),
        "status_code": result.get("status_code"),
        "url": result.get("url"),
        "response_headers": result.get("headers"),
    }


@router.post("/extract")
async def api_extract(
    request: ExtractRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_scraping()
    fetcher = ScrapingFetcher()
    extractor = DataExtractor()
    fetch_result = await fetcher.fetch(str(request.url))
    if not fetch_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(fetch_result.get("error") or "fetch failed"),
        )
    html = fetch_result.get("html") or ""
    if request.extract_type == "css":
        if not request.css_selector:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="css_selector is required for extract_type=css",
            )
        data = extractor.extract_css(html, request.css_selector)
    elif request.extract_type == "xpath":
        if not request.xpath:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="xpath is required for extract_type=xpath",
            )
        data = extractor.extract_xpath(html, request.xpath)
    else:
        if not request.regex:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="regex is required for extract_type=regex",
            )
        data = extractor.extract_regex(html, request.regex)
    return {"ok": True, "url": str(request.url), "data": data, "count": len(data)}


@router.post("/paginated")
async def api_paginated(
    request: PaginatedRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_scraping()
    fetcher = ScrapingFetcher()
    extractor = DataExtractor()
    paginator = PaginationHandler(fetcher, extractor)

    def extract_fn(html: str, page_url: str) -> Any:
        if request.extract_css:
            return extractor.extract_css(html, request.extract_css)
        return {"html_length": len(html), "url": page_url}

    results = await paginator.scrape_paginated(
        str(request.start_url),
        next_selector=request.next_selector,
        max_pages=request.max_pages,
        extract_func=extract_fn,
    )
    return {"ok": True, "pages": len(results), "data": results}


@router.get("/metadata")
async def api_metadata(
    url: HttpUrl = Query(..., description="Page URL to fetch and parse"),
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_scraping()
    fetcher = ScrapingFetcher()
    extractor = DataExtractor()
    result = await fetcher.fetch(str(url))
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(result.get("error") or "fetch failed"),
        )
    meta = extractor.extract_metadata(result.get("html") or "")
    meta["fetched_url"] = result.get("url")
    meta["http_status"] = str(result.get("status_code") or "")
    return {"ok": True, "metadata": meta}


@router.get("/links")
async def api_links(
    url: HttpUrl = Query(...),
    base_url: HttpUrl | None = Query(default=None),
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_scraping()
    fetcher = ScrapingFetcher()
    extractor = DataExtractor()
    result = await fetcher.fetch(str(url))
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(result.get("error") or "fetch failed"),
        )
    base = str(base_url) if base_url else str(url)
    links = extractor.extract_links(result.get("html") or "", base_url=base)
    return {"ok": True, "url": str(url), "links": links, "count": len(links)}


__all__ = ["router"]
