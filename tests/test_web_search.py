from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

_REQ = httpx.Request("GET", "https://example.com/")

from app.core import config as config_mod
from app.schemas.web_ui import WebResponseSourceItem
from app.services import web_search as ws
from app.services.web_research_intent import should_use_web_search
from app.services.web_search import (
    MissingWebSearchKey,
    WebSearchDisabled,
    format_search_results_for_prompt,
    search_web,
)
from app.services.web_turn_extras import set_web_turn_extra, take_web_turn_extra


@pytest.fixture(autouse=True)
def clear_settings_cache():
    config_mod.get_settings.cache_clear()
    yield
    config_mod.get_settings.cache_clear()


def _settings(**kwargs) -> object:
    base = {
        "nexa_web_search_enabled": True,
        "nexa_web_search_provider": "brave",
        "nexa_web_search_api_key": "test-key-not-real",
        "nexa_web_search_max_results": 5,
    }
    base.update(kwargs)
    return type("S", (), base)()


def test_disabled_raises() -> None:
    with patch("app.services.web_search.get_settings", return_value=_settings(nexa_web_search_enabled=False)):
        with pytest.raises(WebSearchDisabled):
            search_web("hello world")


def test_missing_key_raises() -> None:
    with patch(
        "app.services.web_search.get_settings",
        return_value=_settings(nexa_web_search_enabled=True, nexa_web_search_api_key=""),
    ):
        with pytest.raises(MissingWebSearchKey):
            search_web("hello")


def test_max_results_capped() -> None:
    big = {
        "web": {
            "results": [
                {"url": f"https://x{i}.com", "title": f"T{i}", "description": "d"} for i in range(12)
            ]
        }
    }
    with patch("app.services.web_search.get_settings", return_value=_settings(nexa_web_search_max_results=5)):
        with patch("httpx.Client") as mcl:
            inst = MagicMock()
            mcl.return_value.__enter__.return_value = inst
            inst.get.return_value = httpx.Response(200, json=big, request=_REQ)
            r = search_web("q")
    assert len(r.results) == 5


def test_brave_normalizes() -> None:
    body = {
        "web": {
            "results": [
                {"url": "https://a.io/x", "title": "AT", "description": "AD"},
            ]
        }
    }
    with patch("app.services.web_search.get_settings", return_value=_settings()):
        with patch("httpx.Client") as mcl:
            inst = MagicMock()
            mcl.return_value.__enter__.return_value = inst
            inst.get.return_value = httpx.Response(200, json=body, request=_REQ)
            r = search_web("query one")
    assert r.provider == "brave"
    assert r.results[0].url.startswith("https://a.io")
    assert r.results[0].source_provider == "brave"
    assert "AT" in r.results[0].title


def test_tavily_normalizes() -> None:
    body = {
        "results": [
            {"url": "https://b.io/", "title": "BT", "content": "BC"},
        ]
    }
    with patch("app.services.web_search.get_settings", return_value=_settings(nexa_web_search_provider="tavily")):
        with patch("httpx.Client") as mcl:
            inst = MagicMock()
            mcl.return_value.__enter__.return_value = inst
            inst.post.return_value = httpx.Response(
                200, json=body, request=httpx.Request("POST", "https://api.tavily.com/search")
            )
            r = search_web("q")
    assert r.provider == "tavily"
    assert "BC" in r.results[0].snippet


def test_serpapi_normalizes() -> None:
    body = {
        "organic_results": [
            {"link": "https://c.io/", "title": "CT", "snippet": "CS"},
        ]
    }
    with patch("app.services.web_search.get_settings", return_value=_settings(nexa_web_search_provider="serpapi")):
        with patch("httpx.Client") as mcl:
            inst = MagicMock()
            mcl.return_value.__enter__.return_value = inst
            inst.get.return_value = httpx.Response(200, json=body, request=_REQ)
            r = search_web("q")
    assert r.provider == "serpapi"
    assert r.results[0].url == "https://c.io/"


def test_format_no_secrets() -> None:
    from app.services.web_search import SearchResponse, SearchResult

    sr = SearchResponse(
        query="q",
        provider="brave",
        results=[
            SearchResult(
                title="t",
                url="https://a.com",
                snippet="ok",
                source_provider="brave",
            )
        ],
    )
    t = format_search_results_for_prompt(sr)
    assert "test-key" not in t.lower()
    assert "https://a.com" in t


def test_intent_latest() -> None:
    assert should_use_web_search("What is the latest news on Python 3.14?")


def test_intent_url_check_wins() -> None:
    assert not should_use_web_search("check https://example.com and tell me about products")


def test_intent_boss_suppresses_implicit_search() -> None:
    assert not should_use_web_search("@boss research robotics using agents for a bounded mission")


def test_run_search_or_none_soft_fails_on_provider_error() -> None:
    """Provider/network errors should not return the blocking user-facing blob."""
    from app.services.agent_orchestrator import _run_search_or_none

    with patch("app.services.web_search.search_web", side_effect=RuntimeError("upstream")):
        assert _run_search_or_none(None, "user-1", "What is the latest news on Rust?", is_research=False) is None


def test_system_status_search_row() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    with patch("app.core.security.get_settings") as mgs:
        mgs.return_value = type(
            "S",
            (),
            {
                "nexa_web_api_token": None,
                "nexa_web_origins": "http://localhost:3000",
                "app_name": "Nexa",
                "nexa_web_access_enabled": True,
                "nexa_browser_preview_enabled": False,
                "nexa_web_search_enabled": True,
                "nexa_web_search_provider": "tavily",
                "nexa_web_search_api_key": "x",
            },
        )()
        c = TestClient(app)
        with patch("app.api.routes.web.get_settings", return_value=mgs.return_value):
            with patch("app.api.routes.web.read_heartbeat", return_value={}):
                r = c.get("/api/v1/web/system/status", headers={"X-User-Id": "web_test"})
    assert r.status_code == 200, r.text
    inds = {i["id"]: i for i in r.json()["indicators"]}
    assert "enabled: tavily" in (inds.get("web_search") or {}).get("detail", "")


def test_web_turn_extra_for_search() -> None:
    take_web_turn_extra()  # clear
    set_web_turn_extra(
        "web_search",
        [WebResponseSourceItem(url="https://a.com", title="A")],
    )
    t = take_web_turn_extra()
    assert t.response_kind == "web_search"
    assert t.sources[0].url == "https://a.com"
