"""Unified social posting / reads with hourly rate limiting (Phase 22 + Phase 24)."""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.network_policy.policy import is_egress_allowed, record_egress_attempt
from app.services.social.facebook import FacebookClient
from app.services.social.instagram import InstagramClient
from app.services.social.linkedin import LinkedInClient
from app.services.social.tiktok import TikTokClient
from app.services.social.twitter import TwitterClient

logger = logging.getLogger(__name__)


class SocialPlatform(str, Enum):
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class SocialOrchestrator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._twitter: TwitterClient | None = None
        self._linkedin: LinkedInClient | None = None
        self._facebook: FacebookClient | None = None
        self._instagram: InstagramClient | None = None
        self._tiktok: TikTokClient | None = None
        self._lock = asyncio.Lock()
        self._last_action_monotonic: float = 0.0

    def _min_interval_s(self) -> float:
        cap = max(1, int(getattr(self.settings, "nexa_social_rate_limit_per_hour", 50) or 50))
        return 3600.0 / float(cap)

    async def _throttle(self) -> None:
        async with self._lock:
            gap = self._min_interval_s()
            now = time.monotonic()
            wait = self._last_action_monotonic + gap - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_action_monotonic = time.monotonic()

    @property
    def twitter(self) -> TwitterClient | None:
        if not self.settings.nexa_twitter_enabled:
            return None
        if self._twitter is None:
            self._twitter = TwitterClient(self.settings)
        return self._twitter

    @property
    def linkedin(self) -> LinkedInClient | None:
        if not self.settings.nexa_linkedin_enabled:
            return None
        if self._linkedin is None:
            self._linkedin = LinkedInClient(self.settings)
        return self._linkedin

    @property
    def facebook(self) -> FacebookClient | None:
        if not self.settings.nexa_facebook_enabled:
            return None
        if self._facebook is None:
            self._facebook = FacebookClient(self.settings)
        return self._facebook

    @property
    def instagram(self) -> InstagramClient | None:
        if not self.settings.nexa_instagram_enabled:
            return None
        if self._instagram is None:
            self._instagram = InstagramClient(self.settings)
        return self._instagram

    @property
    def tiktok(self) -> TikTokClient | None:
        if not self.settings.nexa_tiktok_enabled:
            return None
        if self._tiktok is None:
            self._tiktok = TikTokClient(self.settings)
        return self._tiktok

    def _download_https_media(self, url: str) -> tuple[bytes | None, str | None]:
        u = (url or "").strip()
        if not u.lower().startswith("https://"):
            return None, "only_https_urls_supported"
        if not is_egress_allowed(u, "social_media_download", None):
            record_egress_attempt(
                url=u,
                purpose="social_media_download",
                user_id=None,
                allowed=False,
                detail="host_not_in_allowlist",
            )
            return None, "egress_not_allowed_add_host_to_NEXA_NETWORK_ALLOWED_HOSTS"
        max_b = max(1, int(self.settings.nexa_social_max_media_size_mb or 10)) * 1024 * 1024
        try:
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                with client.stream("GET", u) as r:
                    if r.status_code >= 400:
                        return None, f"download_http_{r.status_code}"
                    buf = bytearray()
                    for chunk in r.iter_bytes(65536):
                        buf.extend(chunk)
                        if len(buf) > max_b:
                            return None, "media_exceeds_NEXA_SOCIAL_MAX_MEDIA_SIZE_MB"
                    return bytes(buf), None
        except Exception as exc:  # noqa: BLE001
            logger.warning("social download failed: %s", exc)
            return None, "download_failed"

    async def post(
        self,
        platform: SocialPlatform,
        content: str,
        media_urls: list[str] | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.nexa_social_enabled:
            return {"ok": False, "error": "social_disabled", "detail": "Set NEXA_SOCIAL_ENABLED=true"}
        await self._throttle()

        if platform == SocialPlatform.TWITTER:
            tw = self.twitter
            if not tw:
                return {"ok": False, "error": "twitter_disabled"}
            return await asyncio.to_thread(tw.post_tweet, content, reply_to)

        if platform == SocialPlatform.LINKEDIN:
            li = self.linkedin
            if not li:
                return {"ok": False, "error": "linkedin_disabled"}
            return await asyncio.to_thread(li.post_share, content)

        if platform == SocialPlatform.FACEBOOK:
            fb = self.facebook
            if not fb:
                return {"ok": False, "error": "facebook_disabled"}
            return await asyncio.to_thread(fb.post_page_feed, content)

        if platform == SocialPlatform.INSTAGRAM:
            ig = self.instagram
            if not ig:
                return {"ok": False, "error": "instagram_disabled"}
            return await asyncio.to_thread(ig.post_feed, content, media_urls)

        if platform == SocialPlatform.TIKTOK:
            tk = self.tiktok
            if not tk:
                return {"ok": False, "error": "tiktok_disabled"}
            urls = [x.strip() for x in (media_urls or []) if (x or "").strip()]
            if not urls:
                return {
                    "ok": False,
                    "error": "tiktok_requires_media",
                    "detail": "Provide media_urls[0] as a public https URL to an MP4/MOV (downloaded then uploaded)",
                }
            video_bytes, err = await asyncio.to_thread(self._download_https_media, urls[0])
            if err or not video_bytes:
                return {"ok": False, "error": "tiktok_download_failed", "detail": err or "empty_body"}
            return await asyncio.to_thread(tk.upload_video, video_bytes, content)

        return {"ok": False, "error": "unknown_platform"}

    async def get_posts(
        self, platform: SocialPlatform, user_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        if not self.settings.nexa_social_enabled:
            return []
        await self._throttle()
        if platform != SocialPlatform.TWITTER:
            return []
        tw = self.twitter
        if not tw:
            return []
        return await asyncio.to_thread(tw.get_tweets, user_id, limit)

    async def search(
        self, platform: SocialPlatform, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        if not self.settings.nexa_social_enabled:
            return []
        await self._throttle()
        if platform != SocialPlatform.TWITTER:
            return []
        tw = self.twitter
        if not tw:
            return []
        return await asyncio.to_thread(tw.search_tweets, query, limit)


__all__ = ["SocialOrchestrator", "SocialPlatform"]
