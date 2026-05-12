# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Structured extraction — CSS, XPath, regex, tables, metadata, JSON-LD (Phase 21)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from lxml import html as lxml_html

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extract structured data from HTML."""

    def extract_css(self, html_content: str, selector: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        elements = soup.select(selector)
        return [el.get_text(strip=True) for el in elements]

    def extract_xpath(self, html_content: str, xpath: str) -> list[str]:
        tree = lxml_html.fromstring(html_content)
        elements = tree.xpath(xpath)
        out: list[str] = []
        for el in elements:
            if isinstance(el, str):
                out.append(el.strip())
            else:
                try:
                    out.append(el.text_content().strip())
                except Exception:  # noqa: BLE001
                    out.append(str(el).strip())
        return out

    def extract_regex(self, text: str, pattern: str) -> list[str]:
        compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        return compiled.findall(text)

    def extract_table(self, html_content: str, table_selector: str = "table") -> list[list[str]]:
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.select_one(table_selector)
        if not table:
            return []
        result: list[list[str]] = []
        for row in table.find_all("tr"):
            row_data = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
            if row_data:
                result.append(row_data)
        return result

    def extract_links(self, html_content: str, base_url: str | None = None) -> list[dict[str, str]]:
        soup = BeautifulSoup(html_content, "html.parser")
        links: list[dict[str, str]] = []
        base = (base_url or "").strip()
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            text = a.get_text(strip=True)
            if base:
                href = urljoin(base, href)
            links.append({"text": text, "href": href})
        return links

    def extract_metadata(self, html_content: str) -> dict[str, str]:
        soup = BeautifulSoup(html_content, "html.parser")
        metadata: dict[str, str] = {}
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                metadata[str(name)] = str(content)
        canonical = soup.find("link", rel=lambda x: x and "canonical" in str(x).lower())
        if canonical and canonical.get("href"):
            metadata["canonical_url"] = str(canonical["href"])
        return metadata

    def extract_schema_org(self, html_content: str) -> list[Any]:
        soup = BeautifulSoup(html_content, "html.parser")
        schemas: list[Any] = []
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                schemas.append(data)
            except (json.JSONDecodeError, TypeError):
                continue
        return schemas


__all__ = ["DataExtractor"]
