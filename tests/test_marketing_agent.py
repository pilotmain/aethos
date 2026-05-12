# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Marketing agent: public URL + web search should inform replies (not deny tools)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import agent_orchestrator
from app.services.web_access import PublicPageSummary
from app.services.web_research_intent import (
    extract_urls_from_text,
    should_use_marketing_supplemental_web_search,
)
from app.services.web_turn_extras import take_web_turn_extra


def test_marketing_supplemental_search_allows_strong_phrase_with_url() -> None:
    assert should_use_marketing_supplemental_web_search(
        "do web search on pilotmain.com and summarize products and marketing"
    )
    # Direct page read (no "web search" style intent) with URL: skip supplemental search
    assert not should_use_marketing_supplemental_web_search("check this site https://a.com/ products?")


@patch("app.services.safe_llm_gateway.safe_llm_text_call", return_value="I checked the site. Products: LifeOS, ….")
@patch("app.core.config.get_settings")
@patch("app.services.agent_orchestrator._run_marketing_search_block_for_prompt", return_value=(None, []))
@patch("app.services.web_access.summarize_public_page")
def test_marketing_with_url_uses_fetch_and_may_not_say_cant_browse(
    m_sum, _search, m_gets, _llm
) -> None:
    take_web_turn_extra()  # clear
    m_gets.return_value = MagicMock(
        use_real_llm=True,
        openai_api_key="test",
        anthropic_api_key="",
        nexa_web_access_enabled=True,
    )
    m_sum.return_value = PublicPageSummary(
        source_url="https://pilotmain.com/",
        title="P",
        meta_description="M",
        text_excerpt="LifeOS ProposalPilot InvoicePilot QuotePilot DocuPilot" * 20,
        ok=True,
    )
    out = agent_orchestrator.handle_marketing_agent_request(
        MagicMock(), "u1", "@marketing summarize pilotmain.com products and angles"
    )
    assert m_sum.called
    low = (out or "").lower()
    assert "i can't" not in low
    assert "can't perform" not in low
    assert "can't browse" not in low
    assert "marketing agent" in low


@patch("app.services.safe_llm_gateway.safe_llm_text_call", return_value="I used search and the page. Products: A.")
@patch("app.services.web_search.search_web")
@patch("app.core.config.get_settings")
@patch("app.services.web_access.summarize_public_page")
def test_marketing_web_search_phrase_with_url_invokes_search_tool(
    m_sum, m_gets, m_search, _llm
) -> None:
    take_web_turn_extra()  # clear
    m_gets.return_value = MagicMock(
        use_real_llm=True,
        openai_api_key="k",
        anthropic_api_key="",
        nexa_web_access_enabled=True,
        nexa_web_search_enabled=True,
        nexa_web_search_provider="tavily",
        nexa_web_search_api_key="k",
    )
    m_sum.return_value = PublicPageSummary(
        source_url="https://pilotmain.com/",
        title="P",
        meta_description="M",
        text_excerpt="ProductA " * 100,
        ok=True,
    )
    from app.services.web_search import SearchResponse, SearchResult

    m_search.return_value = SearchResponse(
        query="pilotmain",
        provider="tavily",
        results=[
            SearchResult(
                title="P",
                url="https://pilotmain.com/",
                snippet="ProductA",
                source_provider="tavily",
            )
        ],
    )
    out = agent_orchestrator.handle_marketing_agent_request(
        MagicMock(),
        "u1",
        "do web search on pilotmain.com and summarize products and how we can market them",
    )
    assert m_search.called
    q = m_search.call_args[0][0]
    assert "site:" in (q or "").lower() and "pilotmain" in (q or "").lower()
    ex = take_web_turn_extra()
    assert (ex.response_kind or "") == "marketing_web_analysis"
    assert "Web search" in (ex.tool_line or "")
    assert "Public web read" in (ex.tool_line or "")
    low = (out or "").lower()
    assert "i can't" not in low
    assert "can't perform" not in low
    assert "can't browse" not in low


def test_marketing_with_tools_system_prompt_includes_output_sections() -> None:
    s = agent_orchestrator._MARKETING_SYS_WITH_TOOLS
    for part in (
        "What I found",
        "Insight",
        "Positioning",
        "Marketing angles",
        "Suggested copy",
        "Homepage headline",
        "Subheadline",
        "CTA",
        "LinkedIn post hook",
        "Sources",
        "best positioned",
    ):
        assert part in s


def test_marketing_with_tools_system_prompt_thin_page_and_no_fake_certainty() -> None:
    s = agent_orchestrator._MARKETING_SYS_WITH_TOOLS
    assert "limited product detail" in s
    assert "Do not feign certainty" in s
    assert "When the evidence is solid" in s
    assert "qualify briefly" in s


def test_bare_www_and_multi_label_hosts_normalize_to_https() -> None:
    u = extract_urls_from_text("compare www.pilotmain.com and app.pilot.io today", max_urls=4)
    assert u[0].lower().startswith("https://www.pilotmain.com")
    u2 = extract_urls_from_text("read https://www.pilotmain.com/f only once", max_urls=3)
    assert len(u2) == 1
    assert "pilotmain.com" in (u2[0] or "").lower()


@patch("app.services.safe_llm_gateway.safe_llm_text_call", return_value="ok")
@patch("app.core.config.get_settings")
@patch("app.services.web_access.summarize_public_page")
@patch("app.services.agent_orchestrator._run_marketing_search_block_for_prompt", return_value=(None, []))
def test_marketing_sets_public_web_response_kind_with_source_url(
    m_run, m_sum, m_gets, _llm
) -> None:
    m_gets.return_value = MagicMock(
        use_real_llm=True,
        openai_api_key="k",
        anthropic_api_key="",
        nexa_web_access_enabled=True,
    )
    m_sum.return_value = PublicPageSummary(
        source_url="https://pilotmain.com/",
        title="P",
        meta_description="M",
        text_excerpt="ProductA " * 100,
        ok=True,
    )
    take_web_turn_extra()
    agent_orchestrator.handle_marketing_agent_request(
        MagicMock(), "u1", "summarize products for https://pilotmain.com in marketing"
    )
    ex = take_web_turn_extra()
    assert (ex.response_kind or "") == "marketing_web_analysis"
    assert (ex.tool_line or "").startswith("Tool:")
    assert "Public web read" in (ex.tool_line or "")
    assert any("pilotmain.com" in (s.url or "") for s in (ex.sources or []))
