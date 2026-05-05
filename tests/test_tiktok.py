"""Phase 24 — TikTok upload client (mocked HTTP)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.social.tiktok import TikTokClient


def test_tiktok_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    get_settings.cache_clear()
    c = TikTokClient()
    out = c.upload_video(b"x", "cap")
    assert out.get("ok") is False
    assert out.get("error") == "tiktok_not_configured"
    get_settings.cache_clear()


def test_tiktok_upload_single_chunk_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "act_test")
    get_settings.cache_clear()

    class _Resp:
        def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def json(self) -> dict:
            return self._payload

    init_payload = {
        "data": {
            "publish_id": "p1",
            "upload_url": "https://open-upload.tiktokapis.com/video/?x=1",
        },
        "error": {"code": "ok"},
    }
    status_payload = {"data": {"status": "PUBLISH_COMPLETE"}}

    posts: list[tuple] = []
    puts: list = []

    class _Client:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def post(self, url: str, headers: dict | None = None, json: dict | None = None) -> _Resp:
            posts.append((url, json))
            if "status/fetch" in url:
                return _Resp(payload=status_payload)
            return _Resp(payload=init_payload)

        def put(self, upload_url: str, content: bytes, headers: dict) -> _Resp:
            puts.append((upload_url, content, headers))
            return _Resp()

    monkeypatch.setattr("app.services.social.tiktok.httpx.Client", _Client)

    c = TikTokClient()
    vid = b"x" * 100  # under 5MB single chunk
    out = c.upload_video(vid, "hello")
    assert out.get("ok") is True
    assert out.get("publish_id") == "p1"
    assert len(puts) == 1
    get_settings.cache_clear()
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
