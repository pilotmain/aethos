# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Facebook Page feed via Graph API (Phase 22). Instagram uses :mod:`app.services.social.instagram`."""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_GRAPH = "https://graph.facebook.com/v21.0"


class FacebookClient:
    """Publish text posts to a Facebook Page via the Graph API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._page_token = (self._s.facebook_page_access_token or "").strip() or None
        self._page_id = (self._s.facebook_page_id or "").strip() or None

    def post_page_feed(self, message: str) -> dict[str, Any]:
        if not self._page_token or not self._page_id:
            return {
                "ok": False,
                "error": "missing_facebook_config",
                "detail": "Set FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID",
            }
        r = requests.post(
            f"{_GRAPH}/{self._page_id}/feed",
            data={
                "message": message[:8000],
                "access_token": self._page_token,
            },
            timeout=30.0,
        )
        try:
            data = r.json() if r.text else {}
        except Exception:  # noqa: BLE001
            data = {"raw": (r.text or "")[:2000]}
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": "facebook_post_failed",
                "status_code": r.status_code,
                "data": data,
            }
        return {"ok": True, "data": data}


__all__ = ["FacebookClient"]
