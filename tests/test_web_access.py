"""Phase 1: public read-only URL fetch, SSRF blocks, and research wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.services import web_access
from app.services import agent_orchestrator
from app.services.web_access import _assert_url_safe, extract_visible_text, summarize_public_page
from app.services.web_research_intent import should_use_public_url_read

_HTML = b"""<!doctype html><html><head><title>Co</title></head>
<body><script>no</script><p>ProductA</p><p>ServiceB</p></body></html>"""


def test_block_loopback_for_guest() -> None:
    _p, e = _assert_url_safe("http://127.0.0.1/", allow_internal=False)
    assert e


def test_block_private_for_guest() -> None:
    _p, e = _assert_url_safe("http://192.168.1.1/x", allow_internal=False)
    assert e


def test_extract_visible_text_strips_script() -> None:
    t = _HTML.decode("utf-8", errors="replace")
    out = extract_visible_text(t, max_chars=2_000)
    assert "ProductA" in out
    assert "ServiceB" in out


@patch("app.services.web_access.can_fetch_robots_txt", return_value=(True, None))
@patch("app.services.web_access.httpx.Client")
def test_fetch_mock_ok(client_cls, _r) -> None:
    m_c = MagicMock()
    m_c.__enter__.return_value = m_c
    m_c.__exit__ = lambda *_: None
    m_s = m_c.stream
    r = MagicMock()
    r.history = []
    r.status_code = 200
    r.url = "https://example.com/"
    r.headers = {"content-type": "text/html"}
    m_s.return_value = m_s
    m_s.__enter__ = lambda *a: r
    m_s.__exit__ = lambda *a, **k: None
    r.iter_bytes.return_value = [_HTML]
    client_cls.return_value = m_c
    w = web_access.fetch_url("https://example.com/", allow_internal=False, respect_robots=False)
    assert w.status_code == 200
    assert "ProductA" in w.body_text


@patch("app.services.web_access.can_fetch_robots_txt", return_value=(True, None))
@patch("app.services.web_access.httpx.Client")
def test_timeout(client_cls, _r) -> None:
    m_c = MagicMock()
    m_c.__enter__.return_value = m_c
    m_c.__exit__ = lambda *_: None
    m_c.stream = MagicMock(side_effect=httpx.ReadTimeout("t"))
    client_cls.return_value = m_c
    w = web_access.fetch_url("https://example.com/f", allow_internal=False, respect_robots=False)
    assert w.error
    e = (w.error or "").lower()
    assert "time" in e or "failed" in e


@patch("app.services.web_access.fetch_url")
def test_summarize_uses_content(mock_f) -> None:
    mock_f.return_value = web_access.WebFetchResult(
        "u", 200, "u", "text/html", "<html><body><p>X</p></body></html>", False, None, ""
    )
    s = summarize_public_page("https://a.io/", allow_internal=False)
    assert s.ok
    assert "X" in (s.text_excerpt or "")


def test_should_use_public_url_read() -> None:
    assert should_use_public_url_read("Check pilotmain.com and what products?")
    assert should_use_public_url_read("pilotmain.com")
    assert should_use_public_url_read("check this site https://a.com/ ok")
    assert not should_use_public_url_read("I once went to boston and mentioned example.com")


@patch("app.services.web_research_intent.extract_urls_from_text", return_value=["https://x/"])
@patch("app.services.agent_orchestrator._public_url_read_response", return_value="TOOL_OUT")
def test_research_uses_fetched(m_pub, m_e) -> None:
    out = agent_orchestrator.handle_research_agent_request(
        MagicMock(), "u1", "read https://example.com", conversation_snapshot={}
    )
    assert "TOOL_OUT" in out
    m_pub.assert_called()


@patch("app.services.behavior_engine.apply_tone", side_effect=lambda t, m: t)
@patch("app.services.behavior_engine.build_context", return_value=MagicMock(memory={}))
@patch("app.services.intent_classifier.get_intent", return_value="clarify")
@patch("app.core.config.get_settings")
@patch("app.services.agent_orchestrator._public_url_read_response", return_value="G_OUT")
@patch("app.services.web_research_intent.should_use_public_url_read", return_value=True)
def test_nexa_general_path_uses_read(
    _su, _purl, m_gets, _gi, _bctx, _at
) -> None:
    m_gets.return_value = MagicMock(nexa_web_access_enabled=True)
    out = agent_orchestrator.handle_nexa_request(
        MagicMock(),
        "tg_1",
        "please check https://example.com",
        memory_service=MagicMock(),
        orchestrator=MagicMock(),
    )
    assert "G_OUT" in out
    _purl.assert_called()


@patch("app.services.behavior_engine.apply_tone", side_effect=lambda t, m: t)
@patch("app.services.behavior_engine.build_context", return_value=MagicMock(memory={}))
@patch("app.services.intent_classifier.get_intent", return_value="clarify")
@patch("app.core.config.get_settings")
@patch("app.services.agent_orchestrator._public_url_read_response", return_value="OK from public fetch")
@patch("app.services.web_research_intent.should_use_public_url_read", return_value=True)
def test_regression_no_cant_browse_when_tool_ran(
    _su, _purl, m_gets, _gi, _bctx, _at
) -> None:
    """If the public URL path runs, we must not surface general 'can't browse' copy."""
    m_gets.return_value = MagicMock(nexa_web_access_enabled=True)
    with patch(
        "app.services.general_answer_service.answer_general_question",
        return_value="I can't browse the web.",
    ):
        out = agent_orchestrator.handle_nexa_request(
            MagicMock(),
            "tg_1",
            "check this site https://example.com and products",
            memory_service=MagicMock(),
            orchestrator=MagicMock(),
        )
    assert "can't browse" not in (out or "").lower()
    assert "OK from public fetch" in out
    _purl.assert_called()
