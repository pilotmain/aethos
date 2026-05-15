# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""ClawHub HTTP client (Phase 17) — search, metadata, download."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.services.skills.clawhub_models import ClawHubSkillInfo
from app.services.skills.registry_fallback import (
    filter_skill_dicts,
    find_skill_dict,
    merged_fallback_skill_dicts,
    sort_by_downloads,
)

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

    def _fallback_allowed(self) -> bool:
        return bool(getattr(self.settings, "nexa_clawhub_fallback_enabled", True))

    def _parse_skill_info(self, data: dict[str, Any]) -> ClawHubSkillInfo:
        name = str(data.get("name") or data.get("id") or "unknown").strip()
        ver = str(data.get("version") or data.get("latest_version") or "0.0.0").strip()
        publisher = str(data.get("publisher") or data.get("namespace") or "community").strip()
        tags = data.get("tags") if isinstance(data.get("tags"), list) else []
        tags_s = [str(t).strip() for t in tags if str(t).strip()]
        # Phase 75 — single-axis category. Derive from explicit field if present;
        # otherwise fall back to the first tag so the UI filter chips still work
        # against registries that only ship tags. Always normalised to lowercase.
        category_raw = (
            str(data.get("category") or data.get("section") or "").strip().lower()
        )
        if not category_raw and tags_s:
            category_raw = tags_s[0].lower()
        # Phase 75 — cross-skill deps live on a separate ``skill_dependencies``
        # key so the existing ``dependencies`` (pip packages) channel stays
        # untouched. Permissions follow the same shape as the local SkillManifest.
        deps_raw = data.get("skill_dependencies")
        deps_s = (
            [str(d).strip() for d in deps_raw if str(d).strip()]
            if isinstance(deps_raw, list)
            else []
        )
        perms_raw = data.get("permissions")
        perms_s = (
            [str(p).strip().lower() for p in perms_raw if str(p).strip()]
            if isinstance(perms_raw, list)
            else []
        )
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
            category=category_raw,
            readme_url=str(data.get("readme_url") or data.get("readme") or "").strip(),
            changelog_url=str(
                data.get("changelog_url") or data.get("changelog") or ""
            ).strip(),
            skill_dependencies=deps_s,
            permissions=perms_s,
        )

    async def search_skills(
        self,
        query: str,
        limit: int = 20,
        *,
        category: str | None = None,
    ) -> list[ClawHubSkillInfo]:
        q = (query or "").strip()
        if not self._enabled() or not q:
            return []
        url = f"{self.base_url}/skills/search"
        params: dict[str, str | int] = {"q": q, "limit": limit}
        cat = (category or "").strip().lower()
        if cat:
            params["category"] = cat
        data: dict[str, Any] | list[Any] | None = None
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(url, params=params)
                if r.status_code != 200:
                    logger.warning("clawhub search HTTP %s", r.status_code)
                else:
                    try:
                        data = r.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("clawhub search JSON parse failed: %s", exc)
                        data = None
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub search failed: %s", exc)
            data = None
        items = _coerce_skill_list(data) if data is not None else []
        results = [self._parse_skill_info(x) for x in items[: max(1, limit)]]
        # Defensive client-side filter — registries that ignore the ``category``
        # query param still get filtered down so the UI behavior is consistent.
        if cat:
            results = [r for r in results if r.category == cat]
        if results:
            return results
        if self._fallback_allowed():
            fb = filter_skill_dicts(
                merged_fallback_skill_dicts(self.settings),
                query=q,
                category=cat or None,
                limit=limit,
            )
            out = [self._parse_skill_info(x) for x in fb]
            if out:
                logger.info(
                    "clawhub search using fallback catalog (%s hits for q=%r)",
                    len(out),
                    q,
                )
            return out
        return []

    async def get_skill_info(self, name: str) -> ClawHubSkillInfo | None:
        nm = (name or "").strip()
        if not self._enabled() or not nm:
            return None
        url = f"{self.base_url}/skills/{quote(nm, safe='')}"
        data: dict[str, Any] | None = None
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    raw = r.json()
                    data = raw if isinstance(raw, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub get_skill_info failed: %s", exc)
            data = None
        if isinstance(data, dict):
            return self._parse_skill_info(data)
        if self._fallback_allowed():
            fd = find_skill_dict(merged_fallback_skill_dicts(self.settings), nm)
            if fd:
                logger.info("clawhub get_skill_info using fallback for %s", nm)
                return self._parse_skill_info(fd)
        return None

    async def list_popular(self, limit: int = 20) -> list[ClawHubSkillInfo]:
        if not self._enabled():
            return []
        url = f"{self.base_url}/skills/popular"
        data: dict[str, Any] | list[Any] | None = None
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(url, params={"limit": limit})
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("clawhub popular JSON parse failed: %s", exc)
                        data = None
                else:
                    logger.warning("clawhub popular HTTP %s", r.status_code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub popular failed: %s", exc)
            data = None
        items = _coerce_skill_list(data) if data is not None else []
        results = [self._parse_skill_info(x) for x in items[: max(1, limit)]]
        if results:
            return results
        if self._fallback_allowed():
            rows = sort_by_downloads(merged_fallback_skill_dicts(self.settings))
            out = [self._parse_skill_info(x) for x in rows[: max(1, limit)]]
            if out:
                logger.info("clawhub popular using fallback catalog (%s skills)", len(out))
            return out
        return []

    async def list_featured(self, limit: int = 12) -> list[ClawHubSkillInfo]:
        """Phase 75 — best-effort fetch of the registry's curated "featured" set.

        Returns ``[]`` on 404 / network failure / disabled flag — operators with
        a ClawHub registry that doesn't expose ``/skills/featured`` should expect
        an empty list, not an exception. The marketplace UI hides the row when
        the response is empty.
        """
        if not self._enabled():
            return []
        url = f"{self.base_url}/skills/featured"
        data: dict[str, Any] | list[Any] | None = None
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(url, params={"limit": limit})
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("clawhub featured JSON parse failed: %s", exc)
                        data = None
                else:
                    logger.info("clawhub featured HTTP %s (skipping)", r.status_code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("clawhub featured failed: %s", exc)
            data = None
        items = _coerce_skill_list(data) if data is not None else []
        results = [self._parse_skill_info(x) for x in items[: max(1, limit)]]
        if results:
            return results
        return []

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

    async def probe_remote(self) -> dict[str, Any]:
        """Cheap health probe for observability (Mission Control registry status)."""

        base = self.base_url
        out: dict[str, Any] = {
            "base_url": base,
            "reachable": False,
            "http_status": None,
            "json_ok": False,
            "fallback_enabled": self._fallback_allowed(),
            "fallback_skill_count": len(merged_fallback_skill_dicts(self.settings)),
        }
        if not self._enabled():
            out["reason"] = "clawhub_disabled"
            return out
        url = f"{base}/skills/popular"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                r = await client.get(url, params={"limit": 1})
                out["http_status"] = r.status_code
                if r.status_code == 200:
                    try:
                        r.json()
                        out["json_ok"] = True
                        out["reachable"] = True
                    except Exception:
                        out["json_ok"] = False
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)[:300]
        return out


def _coerce_skill_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        inner = data.get("results") or data.get("skills") or data.get("items") or data.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


__all__ = ["ClawHubClient"]
