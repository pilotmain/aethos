# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Instagram Graph API — feed posts (single image/video, carousel) — Phase 24."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_GRAPH_VER = "v21.0"
_GRAPH_BASE = f"https://graph.facebook.com/{_GRAPH_VER}"

# Carousel supports up to 10 images per Meta docs
_MAX_CAROUSEL_ITEMS = 10


class InstagramClient:
    """Create media containers and publish to IG Business/Creator feed."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._ig_user_id = (self._s.instagram_business_account_id or "").strip() or None
        token = (getattr(self._s, "instagram_page_access_token", None) or "").strip()
        if not token:
            token = (self._s.facebook_page_access_token or "").strip()
        self._token = token or None

    def _configured(self) -> bool:
        return bool(self._token and self._ig_user_id)

    def _missing(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "instagram_not_configured",
            "detail": (
                "Set NEXA_INSTAGRAM_ENABLED=true, INSTAGRAM_BUSINESS_ACCOUNT_ID, "
                "and INSTAGRAM_PAGE_ACCESS_TOKEN or FACEBOOK_PAGE_ACCESS_TOKEN"
            ),
        }

    def create_media_container(
        self,
        *,
        image_url: str | None = None,
        video_url: str | None = None,
        caption: str = "",
        is_carousel_item: bool = False,
        media_type: str | None = None,
        children: list[str] | None = None,
    ) -> str:
        """Post to ``/{ig-user-id}/media``. Returns creation ``id`` (container id)."""
        if not self._configured():
            raise RuntimeError("instagram_not_configured")
        params: dict[str, Any] = {
            "access_token": self._token,
        }
        cap = (caption or "")[:2200]
        if children:
            params["media_type"] = "CAROUSEL"
            params["children"] = ",".join(children)
            if cap:
                params["caption"] = cap
        elif is_carousel_item:
            params["is_carousel_item"] = "true"
            if image_url:
                params["image_url"] = image_url
        elif media_type == "VIDEO" or video_url:
            params["media_type"] = "VIDEO"
            params["video_url"] = video_url or ""
            if cap:
                params["caption"] = cap
        elif image_url:
            params["image_url"] = image_url
            if cap:
                params["caption"] = cap
        else:
            raise ValueError("image_url or video_url required")

        url = f"{_GRAPH_BASE}/{self._ig_user_id}/media"
        with httpx.Client(timeout=120.0) as client:
            r = client.post(url, data=params)
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            data = {"raw": (r.text or "")[:2000]}
        if r.status_code >= 400:
            raise RuntimeError(str(data))
        cid = data.get("id")
        if not cid:
            raise RuntimeError(str(data))
        return str(cid)

    def create_video_container(self, video_url: str, caption: str = "") -> str:
        """Create a VIDEO container (feed video); caller must wait until FINISHED before publish."""
        return self.create_media_container(video_url=video_url, caption=caption, media_type="VIDEO")

    def publish_container(self, creation_id: str) -> dict[str, Any]:
        """``/{ig-user-id}/media_publish`` with ``creation_id``."""
        if not self._configured():
            return self._missing()
        params = {"creation_id": creation_id, "access_token": self._token}
        url = f"{_GRAPH_BASE}/{self._ig_user_id}/media_publish"
        with httpx.Client(timeout=120.0) as client:
            r = client.post(url, data=params)
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            data = {"raw": (r.text or "")[:2000]}
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": "instagram_publish_failed",
                "status_code": r.status_code,
                "data": data,
            }
        return {"ok": True, "data": data}

    def _container_status(self, container_id: str) -> str | None:
        q = urlencode(
            {
                "fields": "status_code,status",
                "access_token": self._token or "",
            }
        )
        url = f"{_GRAPH_BASE}/{container_id}?{q}"
        with httpx.Client(timeout=60.0) as client:
            r = client.get(url)
        if r.status_code >= 400:
            return None
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            return None
        return str(data.get("status_code") or data.get("status") or "")

    def _wait_video_ready(self, container_id: str, *, max_wait_s: float = 120.0) -> dict[str, Any]:
        deadline = time.monotonic() + max_wait_s
        last = ""
        while time.monotonic() < deadline:
            st = self._container_status(container_id) or ""
            last = st
            if st in ("FINISHED", "PUBLISHED"):
                return {"ok": True, "status_code": st}
            if st in ("ERROR", "EXPIRED"):
                return {"ok": False, "error": "instagram_video_processing_failed", "status_code": st}
            time.sleep(2.0)
        return {"ok": False, "error": "instagram_video_timeout", "last_status": last}

    def post_feed(
        self,
        caption: str,
        media_urls: list[str] | None = None,
        *,
        media_type: str = "image",
    ) -> dict[str, Any]:
        """
        Full flow: single image URL, single video URL, or multiple image URLs (carousel).

        ``media_type`` hints ``image`` | ``video`` for single-URL disambiguation.
        """
        if not self._configured():
            return self._missing()
        urls = [u.strip() for u in (media_urls or []) if (u or "").strip()]
        if not urls:
            return {
                "ok": False,
                "error": "instagram_needs_media",
                "detail": "Provide at least one public https URL in media_urls",
            }

        try:
            if len(urls) == 1:
                u = urls[0]
                is_video = media_type.lower() == "video" or any(
                    u.lower().endswith(x) for x in (".mp4", ".mov", ".m4v")
                )
                if is_video:
                    cid = self.create_video_container(u, caption=caption)
                    wait = self._wait_video_ready(cid)
                    if not wait.get("ok"):
                        return wait
                    return self.publish_container(cid)
                cid = self.create_media_container(image_url=u, caption=caption)
                return self.publish_container(cid)

            # Carousel (images only)
            if len(urls) > _MAX_CAROUSEL_ITEMS:
                return {
                    "ok": False,
                    "error": "instagram_carousel_limit",
                    "detail": f"Max {_MAX_CAROUSEL_ITEMS} images",
                }
            child_ids: list[str] = []
            for u in urls:
                cid = self.create_media_container(image_url=u, caption="", is_carousel_item=True)
                child_ids.append(cid)
            carousel_id = self.create_media_container(
                caption=caption,
                children=child_ids,
            )
            return self.publish_container(carousel_id)
        except RuntimeError as exc:
            return {"ok": False, "error": "instagram_graph_error", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("instagram post_feed")
            return {"ok": False, "error": "instagram_exception", "detail": str(exc)}


__all__ = ["InstagramClient"]
