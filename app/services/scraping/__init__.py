"""
Web scraping enhancements (Phase 21) — smart fetch, extraction, pagination.
"""

from app.services.scraping.extractor import DataExtractor
from app.services.scraping.fetcher import ScrapingFetcher
from app.services.scraping.pagination import PaginationHandler

__all__ = ["DataExtractor", "PaginationHandler", "ScrapingFetcher"]
