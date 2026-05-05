"""Scraping CLI — calls Phase 21 fetcher/extractor locally (no API required)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.services.scraping import DataExtractor, PaginationHandler, ScrapingFetcher


def scraping_main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="nexa scrape")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("fetch", help="Fetch URL and print HTML snippet or save to file")
    pf.add_argument("url")
    pf.add_argument("-o", "--output", help="Write full HTML to file")

    pe = sub.add_parser("extract", help="Fetch and extract with CSS, XPath, or regex")
    pe.add_argument("url")
    pe.add_argument("--css", dest="css", default=None)
    pe.add_argument("--xpath", dest="xpath", default=None)
    pe.add_argument("--regex", dest="regex", default=None)

    pp = sub.add_parser("paginate", help="Follow pagination links")
    pp.add_argument("url")
    pp.add_argument("--next-css", default='a[rel="next"]')
    pp.add_argument("--extract-css", default=None)
    pp.add_argument("--max-pages", type=int, default=None)

    ns = p.parse_args(args)

    async def _run() -> int:
        if ns.cmd == "fetch":
            fetcher = ScrapingFetcher()
            out = await fetcher.fetch(ns.url)
            if not out.get("success"):
                print(out.get("error") or "failed", file=sys.stderr)
                return 1
            html = out.get("html") or ""
            if ns.output:
                with open(ns.output, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"Saved {len(html)} characters to {ns.output}")
                return 0
            print(html[:500] + ("..." if len(html) > 500 else ""))
            return 0

        if ns.cmd == "extract":
            fetcher = ScrapingFetcher()
            ex = DataExtractor()
            out = await fetcher.fetch(ns.url)
            if not out.get("success"):
                print(out.get("error") or "fetch failed", file=sys.stderr)
                return 1
            html = out.get("html") or ""
            if ns.css:
                data = ex.extract_css(html, ns.css)
            elif ns.xpath:
                data = ex.extract_xpath(html, ns.xpath)
            elif ns.regex:
                data = ex.extract_regex(html, ns.regex)
            else:
                print("Specify --css, --xpath, or --regex", file=sys.stderr)
                return 2
            print(json.dumps(data, indent=2))
            return 0

        if ns.cmd == "paginate":
            fetcher = ScrapingFetcher()
            ex = DataExtractor()
            paginator = PaginationHandler(fetcher, ex)

            def extract_func(html: str, page_url: str):
                if ns.extract_css:
                    return ex.extract_css(html, ns.extract_css)
                return {"url": page_url, "length": len(html)}

            rows = await paginator.scrape_paginated(
                ns.url,
                next_selector=ns.next_css,
                max_pages=ns.max_pages,
                extract_func=extract_func,
            )
            print(json.dumps({"pages": len(rows), "data": rows}, indent=2)[:24000])
            return 0

        return 2

    return asyncio.run(_run())


__all__ = ["scraping_main"]
