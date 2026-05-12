# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""TikTok Content Posting API — Direct Post video via FILE_UPLOAD (Phase 24)."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_BASE = "https://open.tiktokapis.com"
_VIDEO_INIT = f"{_BASE}/v2/post/publish/video/init/"
_STATUS_FETCH = f"{_BASE}/v2/post/publish/status/fetch/"

# TikTok chunk rules (see media transfer guide): min 5MB per chunk when multi-chunk; max 64MB
_CHUNK_MIN = 5 * 1024 * 1024
_CHUNK_MAX = 64 * 1024 * 1024


class TikTokClient:
    """Upload video bytes with caption using Direct Post (``video/init`` + chunked PUT)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._token = (self._s.tiktok_access_token or "").strip() or None
        self._open_id = (self._s.tiktok_open_id or "").strip() or None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _configured(self) -> bool:
        return bool(self._token)

    def _missing(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "tiktok_not_configured",
            "detail": "Set NEXA_TIKTOK_ENABLED=true and TIKTOK_ACCESS_TOKEN (video.upload scope)",
        }

    def _privacy_level(self) -> str:
        return (getattr(self._s, "tiktok_privacy_level", None) or "SELF_ONLY").strip()

    def upload_video(self, video_bytes: bytes, caption: str) -> dict[str, Any]:
        """
        Initialize Direct Post, upload binary chunks to ``upload_url``, optionally poll status.

        Until your TikTok app passes audit, ``privacy_level`` is often restricted to ``SELF_ONLY``.
        """
        if not self._configured():
            return self._missing()
        size = len(video_bytes)
        max_mb = max(1, int(getattr(self._s, "nexa_social_max_media_size_mb", 10) or 10))
        if size > max_mb * 1024 * 1024:
            return {
                "ok": False,
                "error": "tiktok_video_too_large",
                "detail": f"Max {max_mb} MiB (NEXA_SOCIAL_MAX_MEDIA_SIZE_MB)",
            }

        chunk_size, total_chunks = self._chunk_plan(size)
        post_info: dict[str, Any] = {
            "title": (caption or "")[:2200],
            "privacy_level": self._privacy_level(),
        }
        body: dict[str, Any] = {
            "post_info": post_info,
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

        with httpx.Client(timeout=120.0) as client:
            r = client.post(_VIDEO_INIT, headers=self._headers(), json=body)
            try:
                data = r.json()
            except Exception:  # noqa: BLE001
                data = {"raw": (r.text or "")[:2000]}
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "error": "tiktok_init_failed",
                    "status_code": r.status_code,
                    "data": data,
                }
            if isinstance(data, dict):
                terr = data.get("error")
                if isinstance(terr, dict):
                    code = str(terr.get("code") or "").lower()
                    if code and code != "ok":
                        return {"ok": False, "error": "tiktok_init_error", "data": data}
            inner = data.get("data") if isinstance(data, dict) else None
            if not isinstance(inner, dict):
                return {"ok": False, "error": "tiktok_init_parse", "data": data}
            upload_url = inner.get("upload_url")
            publish_id = inner.get("publish_id")
            if not upload_url or not publish_id:
                return {"ok": False, "error": "tiktok_init_missing_fields", "data": data}

            put_err = self._upload_chunks(client, upload_url, video_bytes, chunk_size)
            if put_err:
                return put_err

        # Poll status briefly so callers get a terminal-ish state when possible
        status = self.get_upload_status(str(publish_id))
        out: dict[str, Any] = {
            "ok": True,
            "publish_id": publish_id,
            "upload_status": status,
        }
        return out

    def _chunk_plan(self, size: int) -> tuple[int, int]:
        if size <= 0:
            raise ValueError("empty video")
        if size <= _CHUNK_MIN:
            return size, 1
        chunk_size = min(_CHUNK_MAX, max(_CHUNK_MIN, size))
        total = max(1, math.ceil(size / chunk_size))
        return chunk_size, total

    def _upload_chunks(
        self,
        client: httpx.Client,
        upload_url: str,
        video_bytes: bytes,
        chunk_size: int,
    ) -> dict[str, Any] | None:
        total = len(video_bytes)
        offset = 0
        chunk_index = 0
        while offset < total:
            end = min(offset + chunk_size, total)
            chunk = video_bytes[offset:end]
            first, last = offset, end - 1
            headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {first}-{last}/{total}",
            }
            r = client.put(upload_url, content=chunk, headers=headers)
            if r.status_code >= 400:
                try:
                    detail = r.json()
                except Exception:  # noqa: BLE001
                    detail = {"text": (r.text or "")[:1500]}
                return {
                    "ok": False,
                    "error": "tiktok_chunk_upload_failed",
                    "status_code": r.status_code,
                    "chunk_index": chunk_index,
                    "detail": detail,
                }
            offset = end
            chunk_index += 1
        return None

    def get_upload_status(self, publish_id: str) -> dict[str, Any]:
        """POST ``/v2/post/publish/status/fetch/`` for a ``publish_id``."""
        if not self._configured():
            return self._missing()
        body = {"publish_id": publish_id}
        deadline = time.monotonic() + 90.0
        last: dict[str, Any] = {}
        with httpx.Client(timeout=60.0) as client:
            while time.monotonic() < deadline:
                r = client.post(_STATUS_FETCH, headers=self._headers(), json=body)
                try:
                    data = r.json()
                except Exception:  # noqa: BLE001
                    data = {"raw": (r.text or "")[:2000]}
                last = data if isinstance(data, dict) else {"raw": data}
                inner = last.get("data") if isinstance(last, dict) else None
                status = None
                if isinstance(inner, dict):
                    status = inner.get("status")
                if status in ("PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"):
                    return last
                if status in ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD") or status is None:
                    time.sleep(2.0)
                    continue
                return last
        return last


__all__ = ["TikTokClient"]
