"""LinkedIn UGC Posts (Phase 22) — text shares only."""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LinkedInClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._token = (self._s.linkedin_access_token or "").strip() or None
        self._author_urn = (self._s.linkedin_person_urn or "").strip() or None

    def post_share(self, text: str) -> dict[str, Any]:
        if not self._token or not self._author_urn:
            return {
                "ok": False,
                "error": "missing_linkedin_config",
                "detail": "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN (urn:li:person:…)",
            }
        body = {
            "author": self._author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text[:3000]},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        r = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=body,
            timeout=30.0,
        )
        try:
            data = r.json() if r.text else {}
        except Exception:  # noqa: BLE001
            data = {"raw": (r.text or "")[:2000]}
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": "linkedin_post_failed",
                "status_code": r.status_code,
                "data": data,
            }
        return {"ok": True, "data": data}


__all__ = ["LinkedInClient"]
