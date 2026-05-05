"""ClawHub HTTP client (Phase 17) — search, metadata, download."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.services.skills.clawhub_models import ClawHubSkillInfo

logger = logging.getLogger(__name__)


def _parse_datetime(raw: object) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw or "").strip()
    if not s:
        return datetime.now(timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class ClawHubClient:
    """Async client for a ClawHub-compatible registry API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        raw = (getattr(self.settings, "nexa_clawhub_api_base", None) or "").strip()
        self.base_url = raw.rstrip("/") or "https://clawhub.com/api/v1"

    def _enabled(self) -> bool:
        return bool(getattr(self.settings, "nexa_clawhub_enabled", True))

    def _parse_skill_info(self, data: dict[str, Any]) -> ClawHubSkillInfo:
        name = str(data.get("name") or data.get("id") or "unknown").strip()
        ver = str(data.get("version") or data.get("latest_version") or "0.0.0").strip()
        publisher = str(data.get("publisher") or data.get("namespace") or "community").strip()
        tags = data.get("tags") if isinstance(data.get("tags"), list) else []
        tags_s = [str(t).strip() for t in tags if str(t).strip()]
        return ClawHubSkillInfo(
            name=name,
            version=ver,
            description=str(data.get("description") or data.get("summary") or "").strip(),
            author=str(data.get("author") or data.get("maintainer") or "unknown").strip(),
            publisher=publisher,
            tags=tags_s,
            downloads=int(data.get("downloads") or data.get("install_count") or 0),
            rating=float(data.get("rating") or data.get("stars") or 0.0),
            updated_at=_parse_datetime(data.get("updated_at") or data.get("updated")),
            signature=(str(data["signature"]).strip() if data.get("signature") else None),
            manifest_url=str(data.get("manifest_url") or "").strip(),
            archive_url=str(data.get("archive_url") or data.get("download_url") or "").strip(),
        )

    async def search_skills(self, query: str, limit: int = 20) -> list[ClawHubSkillInfo]:
        q = (query or "").strip()
        if not self._enabled() or not q:
            return []
        url = f"{self.base_url}/skills/search"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params={"q": q, "limit": limit})
                if r.status_code != 200:
                    logger.warning("clawhub search HTTP %s", r.status_code)
                    return []
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub search failed: %s", exc)
            return []
        items = _coerce_skill_list(data)
        return [self._parse_skill_info(x) for x in items[: max(1, limit)]]

    async def get_skill_info(self, name: str) -> ClawHubSkillInfo | None:
        nm = (name or "").strip()
        if not self._enabled() or not nm:
            return None
        url = f"{self.base_url}/skills/{quote(nm, safe='')}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return None
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub get_skill_info failed: %s", exc)
            return None
        return self._parse_skill_info(data) if isinstance(data, dict) else None

    async def list_popular(self, limit: int = 20) -> list[ClawHubSkillInfo]:
        if not self._enabled():
            return []
        url = f"{self.base_url}/skills/popular"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params={"limit": limit})
                if r.status_code != 200:
                    return []
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub popular failed: %s", exc)
            return []
        items = _coerce_skill_list(data)
        return [self._parse_skill_info(x) for x in items[: max(1, limit)]]

    async def download_skill(self, name: str, version: str = "latest") -> bytes | None:
        nm = (name or "").strip()
        if not self._enabled() or not nm:
            return None
        url = f"{self.base_url}/skills/{quote(nm, safe='')}/download"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.get(url, params={"version": version})
                if r.status_code != 200:
                    return None
                return r.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub download_skill failed: %s", exc)
            return None


def _coerce_skill_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        inner = data.get("results") or data.get("skills") or data.get("items") or data.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


__all__ = ["ClawHubClient"]
