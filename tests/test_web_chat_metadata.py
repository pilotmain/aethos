from __future__ import annotations

from app.services.web_chat_metadata import compute_web_message_metadata


def test_metadata_public_web_research() -> None:
    m = compute_web_message_metadata(
        "@research check https://example.com foo",
        "research",
        "🔎 **Research** (Nexa)\n\nI used public read-only page fetch. x",
    )
    assert m.response_kind == "public_web"
    assert m.sources[0].url.startswith("https://example.com")


def test_metadata_browser_preview() -> None:
    m = compute_web_message_metadata(
        "@research browser preview https://example.com",
        "research",
        "**Page:** T\n\n**Final URL:** https://example.com/other",
    )
    assert m.response_kind == "browser_preview"
    assert m.sources[0].url == "https://example.com/other"


def test_metadata_browser_preview_uses_ask_url_when_no_final() -> None:
    m = compute_web_message_metadata(
        "@research browser preview https://example.com/path",
        "research",
        "NEXA_BROWSER_PREVIEW_ENABLED=false",
    )
    assert m.response_kind == "browser_preview"
    assert m.sources[0].url == "https://example.com/path"


def test_metadata_empty_without_match() -> None:
    m = compute_web_message_metadata("hello world", "nexa", "no urls here")
    assert m.response_kind is None
    assert m.sources == []
