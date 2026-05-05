# Phase 21 — Web scraping enhancements

Nexa adds an **HTTP-first scraping stack** (async `httpx`, BeautifulSoup, lxml) alongside Playwright browser automation (Phase 14). Use scraping for **read-only HTML/JSON fetch**, CSS/XPath extraction, and simple **next-link pagination**.

## Safety

- URLs are validated with the same **SSRF-oriented checks** as `app.services.web_access` (`validate_public_url_strict`).
- Scraping does **not** execute JavaScript. For JS-heavy sites, use **browser automation** APIs instead.

## Configuration (`app/core/config.py`)

| Env | Purpose |
|-----|---------|
| `NEXA_SCRAPING_ENABLED` | Master toggle (default `true`). |
| `NEXA_SCRAPING_MAX_PAGES` | Pagination cap (default `10`, clamped in code). |
| `NEXA_SCRAPING_TIMEOUT_SECONDS` | Per-request timeout (default `30`). |
| `NEXA_SCRAPING_RATE_LIMIT_PER_MINUTE` | Minimum spacing between requests (default `60`/min). |
| `NEXA_SCRAPING_USER_AGENTS` | Empty → built-in UA pool; or JSON array; or `UA1||UA2` (double-pipe). |
| `NEXA_SCRAPING_PROXY_URL` | Optional HTTP(S) proxy for `httpx`. |
| `NEXA_SCRAPING_STEALTH_MODE` | When true, rotate `User-Agent` from the pool (default `true`). |

Sync `.env.example` and local `.env` when changing flags.

## REST API

Prefix: **`/api/v1/scraping`** (`settings.api_v1_prefix`).

Authentication matches **cron** and **browser automation**: header  

`Authorization: Bearer <NEXA_CRON_API_TOKEN>`  

If `NEXA_CRON_API_TOKEN` is unset, endpoints return **503**.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/fetch` | JSON `{ "url", "timeout?", "retries?" }` → HTML + status. |
| POST | `/extract` | Fetch then CSS / XPath / regex (`extract_type`, selectors). |
| POST | `/paginated` | Follow `next_selector` CSS link up to `max_pages`. |
| GET | `/metadata` | Query `url=` → title & meta tags. |
| GET | `/links` | Query `url=` and optional `base_url=` → anchor list. |

## CLI (`python -m nexa_cli`)

Runs **locally** (no API process required):

```bash
python -m nexa_cli scrape fetch https://example.com
python -m nexa_cli scrape fetch https://example.com -o /tmp/page.html
python -m nexa_cli scrape extract https://example.com --css "h1"
python -m nexa_cli scrape paginate https://example.com --next-css 'a.next' --max-pages 3
```

## Python modules

- `app.services.scraping.fetcher` — `ScrapingFetcher`
- `app.services.scraping.extractor` — `DataExtractor`
- `app.services.scraping.pagination` — `PaginationHandler`

## Testing

See `tests/test_scraping.py` (mocked HTTP; no live network required in CI).
