# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Twitter / X API v2 — OAuth 1.0a for writes, Bearer for reads (Phase 22)."""

from __future__ import annotations

import logging
from typing import Any

import requests
from requests_oauthlib import OAuth1

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TwitterClient:
    """Minimal Twitter API v2 client (post via OAuth1; search/timeline via Bearer)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self.api_key = (self._s.twitter_api_key or "").strip() or None
        self.api_secret = (self._s.twitter_api_secret or "").strip() or None
        self.access_token = (self._s.twitter_access_token or "").strip() or None
        self.access_secret = (self._s.twitter_access_secret or "").strip() or None
        self.bearer = (self._s.twitter_bearer_token or "").strip() or None

    def _oauth1(self) -> OAuth1 | None:
        if not all(
            (self.api_key, self.api_secret, self.access_token, self.access_secret)
        ):
            return None
        return OAuth1(
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_secret,
            signature_type="AUTH_HEADER",
        )

    def post_tweet(self, text: str, reply_to: str | None = None) -> dict[str, Any]:
        """POST /2/tweets (OAuth 1.0a user context)."""
        auth = self._oauth1()
        if not auth:
            return {
                "ok": False,
                "error": "missing_twitter_oauth1",
                "detail": "Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET",
            }
        body: dict[str, Any] = {"text": text[:280]}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            json=body,
            auth=auth,
            timeout=30.0,
        )
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            data = {"raw": (r.text or "")[:2000]}
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": "twitter_post_failed",
                "status_code": r.status_code,
                "data": data,
            }
        return {"ok": True, "data": data}

    def get_tweets(self, user_id: str, max_results: int = 10) -> list[dict[str, Any]]:
        """GET /2/users/:id/tweets (Bearer)."""
        if not self.bearer:
            return []
        max_results = max(5, min(int(max_results or 10), 100))
        r = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            headers={"Authorization": f"Bearer {self.bearer}"},
            params={
                "max_results": max_results,
                "tweet.fields": "created_at,public_metrics",
            },
            timeout=30.0,
        )
        if r.status_code >= 400:
            logger.warning("twitter get_tweets failed: %s", r.status_code)
            return []
        try:
            return list((r.json() or {}).get("data") or [])
        except Exception:  # noqa: BLE001
            return []

    def search_tweets(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """GET /2/tweets/search/recent (Bearer; app may need Elevated / paid access)."""
        if not self.bearer:
            return []
        max_results = max(10, min(int(max_results or 10), 100))
        r = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {self.bearer}"},
            params={"query": query, "max_results": max_results},
            timeout=30.0,
        )
        if r.status_code >= 400:
            logger.warning("twitter search failed: %s", r.status_code)
            return []
        try:
            return list((r.json() or {}).get("data") or [])
        except Exception:  # noqa: BLE001
            return []


__all__ = ["TwitterClient"]
