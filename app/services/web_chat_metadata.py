"""Optional metadata for web chat: research + public URL / browser preview (Phase 1)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.web_ui import WebResponseSourceItem


@dataclass
class WebMessageMetadata:
    response_kind: str | None = None
    # public_web | browser_preview | web_search | marketing_web_analysis
    sources: list[WebResponseSourceItem] = field(default_factory=list)
    tool_line: str | None = None


_FINAL_URL_RE = re.compile(r"^\s*\*\*Final URL:\*\*\s*(\S+)", re.M | re.I)
_TITLE_LINE_RE = re.compile(r"^\s*\*\*Page:\*\*\s*(.+)$", re.M)


def _parse_final_url_from_reply(reply: str) -> str | None:
    m = _FINAL_URL_RE.search(reply or "")
    if m:
        u = (m.group(1) or "").strip().rstrip(")`")
        return u if u.startswith("http") else None
    return None


def _page_title_from_reply(reply: str) -> str | None:
    m = _TITLE_LINE_RE.search(reply or "")
    if m:
        t = (m.group(1) or "").strip()
        return t[:500] if t and t != "(no title)" else None
    return None


def compute_web_message_metadata(
    user_text: str,
    agent_key: str | None,
    reply: str,
) -> WebMessageMetadata:
    from app.services.web_research_intent import (
        extract_url_for_browser_preview,
        extract_urls_from_text,
    )

    t = (user_text or "").strip()
    r = reply or ""
    rlower = r.lower()
    key = (agent_key or "").strip() or "nexa"
    is_research = key == "research"

    preview_ask = extract_url_for_browser_preview(t)
    if preview_ask and is_research:
        final_u = _parse_final_url_from_reply(r) or preview_ask
        return WebMessageMetadata(
            "browser_preview",
            [
                WebResponseSourceItem(
                    url=final_u,
                    title=_page_title_from_reply(r),
                )
            ],
        )

    urls = extract_urls_from_text(t, max_urls=3)
    if not urls:
        return WebMessageMetadata()
    is_research_block = "🔎" in r and "research" in rlower
    if (
        is_research
        and is_research_block
        and ("public read-only" in rlower or "public read only" in rlower)
    ) or (key == "nexa" and "public read-only" in rlower):
        return WebMessageMetadata(
            "public_web",
            [WebResponseSourceItem(url=u, title=None) for u in urls],
        )

    return WebMessageMetadata()
