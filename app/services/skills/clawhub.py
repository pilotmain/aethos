"""HTTP-facing helpers for ClawHub-compatible skill registry (Phase 6 + 17)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.services.skills.clawhub_client import ClawHubClient

logger = logging.getLogger(__name__)


async def search_skills(query: str) -> list[dict[str, Any]]:
    """Search remote catalog; returns list of dicts (backward compatible with Phase 6)."""
    if not getattr(get_settings(), "nexa_clawhub_enabled", True):
        return []
    client = ClawHubClient()
    items = await client.search_skills(query)
    return [x.to_dict() for x in items]


async def get_skill_info(name: str) -> dict[str, Any] | None:
    """Remote skill metadata as dict (backward compatible)."""
    client = ClawHubClient()
    info = await client.get_skill_info(name)
    return info.to_dict() if info else None


async def download_skill(name: str, version: str = "latest") -> bytes | None:
    return await ClawHubClient().download_skill(name, version)


__all__ = ["download_skill", "get_skill_info", "search_skills"]
